"""Unit tests for the conversation flow (Phase 3).

Covers the manager, conversation service, and message service with the
fake repository — no live database, no AI, no channels.
"""

from app.models.conversation import ConversationMessageResult
from app.services import conversation_manager, conversation_service, message_service
from app.services.conversation_service import (
    StatusNotFound,
    StatusUpdated,
    StatusValidationFailure,
)
from tests.conversation_fakes import FakeConversationRepository


def _first_message(repo=None, **overrides):
    """Run the manager once with sane local-test defaults."""
    repo = repo or FakeConversationRepository()
    base = {
        "customer_name": "Ana Lopez",
        "customer_phone": "+10000000001",
        "customer_email": "",
        "channel": "local_test",
        "message_text": "Hello, I need catering.",
    }
    base.update(overrides)
    result = conversation_manager.handle_customer_message(
        base["customer_name"],
        base["customer_phone"],
        base["customer_email"],
        base["channel"],
        base["message_text"],
        repo,
    )
    return result, repo


def test_new_customer_conversation_and_first_message() -> None:
    """First message creates customer + active conversation + stored message."""
    result, repo = _first_message()

    assert isinstance(result, ConversationMessageResult)
    assert result.status == "success"
    assert result.conversation_id
    assert result.message_id
    assert result.conversation_status == "active"
    assert result.created_new_conversation is True
    assert result.created_new_customer is True
    assert len(repo.customers) == 1
    assert len(repo.conversations) == 1
    assert len(repo.messages) == 1
    stored = repo.messages[0]
    assert stored["sender"] == "customer"
    assert stored["message"] == "Hello, I need catering."
    assert stored["conversation_id"] == result.conversation_id


def test_existing_customer_reuses_active_conversation() -> None:
    """Second message lands in the same active conversation."""
    result1, repo = _first_message()
    result2, _ = _first_message(repo=repo, message_text="Second message.")

    assert isinstance(result2, ConversationMessageResult)
    assert result2.conversation_id == result1.conversation_id
    assert result2.created_new_conversation is False
    assert result2.created_new_customer is False
    assert len(repo.customers) == 1
    assert len(repo.conversations) == 1
    assert len(repo.messages) == 2


def test_different_customers_remain_isolated() -> None:
    """Two customers get separate customers, conversations, and messages."""
    result_a, repo = _first_message()
    result_b, _ = _first_message(
        repo=repo, customer_phone="+10000000002", message_text="Other customer."
    )

    assert result_a.conversation_id != result_b.conversation_id
    assert result_a.customer_id != result_b.customer_id
    assert len(repo.customers) == 2
    assert len(repo.conversations) == 2
    history_a = message_service.get_history(result_a.conversation_id, repo)
    assert all(message["conversation_id"] == result_a.conversation_id for message in history_a)


def test_messages_preserve_chronological_order() -> None:
    """History returns oldest first as messages accumulate."""
    result, repo = _first_message()
    for text in ("Second.", "Third.", "Fourth."):
        _first_message(repo=repo, message_text=text)

    history = message_service.get_history(result.conversation_id, repo)
    assert [message["message"] for message in history] == [
        "Hello, I need catering.",
        "Second.",
        "Third.",
        "Fourth.",
    ]
    created = [message["created_at"] for message in history]
    assert created == sorted(created)


def test_conversation_history_retrieval() -> None:
    """Detail returns metadata plus the ordered message list."""
    result, repo = _first_message()
    detail = conversation_service.get_conversation_detail(result.conversation_id, repo)

    assert detail is not None
    conversation, messages = detail
    assert conversation["customer_id"] == result.customer_id
    assert conversation["channel"] == "local_test"
    assert conversation["status"] == "active"
    assert len(messages) == 1

    assert conversation_service.get_conversation_detail("missing-id", repo) is None


def test_human_handoff_status_representable() -> None:
    """active → human_handoff is an allowed deterministic transition."""
    result, repo = _first_message()
    outcome = conversation_service.change_conversation_status(
        result.conversation_id, "human_handoff", repo
    )

    assert isinstance(outcome, StatusUpdated)
    assert outcome.conversation["status"] == "human_handoff"


def test_closed_conversation_starts_a_new_one() -> None:
    """A message after closing opens a fresh conversation (closed is terminal)."""
    result1, repo = _first_message()
    closed = conversation_service.change_conversation_status(
        result1.conversation_id, "closed", repo
    )
    assert isinstance(closed, StatusUpdated)

    # Closed threads can never be reopened directly.
    reopened = conversation_service.change_conversation_status(
        result1.conversation_id, "active", repo
    )
    assert isinstance(reopened, StatusValidationFailure)
    assert reopened.errors[0].code == "INVALID_STATUS_TRANSITION"

    # The next message deterministically opens a new active conversation.
    result2, _ = _first_message(repo=repo, message_text="After closing.")
    assert result2.conversation_id != result1.conversation_id
    assert result2.created_new_conversation is True


def test_unknown_status_rejected() -> None:
    """Arbitrary status values never reach the database."""
    result, repo = _first_message()
    outcome = conversation_service.change_conversation_status(
        result.conversation_id, "archived", repo
    )
    assert isinstance(outcome, StatusValidationFailure)
    assert outcome.errors[0].code == "UNSUPPORTED_CONVERSATION_STATUS"
    assert isinstance(
        conversation_service.change_conversation_status("missing-id", "closed", repo),
        StatusNotFound,
    )


def test_invalid_message_request_rejected() -> None:
    """Blank messages and unsupported channels fail before any writes."""
    blank, repo = _first_message(message_text="   ")
    assert blank.status == "validation_error"
    assert blank.errors[0].code == "REQUIRED_MESSAGE"
    assert repo.customers == [] and repo.conversations == []

    bad_channel, repo2 = _first_message(channel="facebook")
    assert bad_channel.status == "validation_error"
    assert bad_channel.errors[0].code == "UNSUPPORTED_CHANNEL"
    assert repo2.customers == [] and repo2.conversations == []


def test_invalid_customer_rejected_per_booking_rules() -> None:
    """Missing name/phone fail exactly like the Phase 2 customer rules."""
    no_name, _ = _first_message(customer_name="  ")
    assert no_name.status == "validation_error"
    assert no_name.errors[0].code == "REQUIRED_CUSTOMER_NAME"

    no_phone, _ = _first_message(customer_phone="")
    assert no_phone.status == "validation_error"
    assert no_phone.errors[0].code == "REQUIRED_CUSTOMER_PHONE"

    bad_email, _ = _first_message(customer_email="not-an-email")
    assert bad_email.status == "validation_error"
    assert bad_email.errors[0].code == "INVALID_EMAIL"


def test_repository_failure_without_raw_exceptions() -> None:
    """DB failures become generic errors, never raw Supabase exceptions."""
    from app.models.conversation import ConversationError

    broken = FakeConversationRepository(fail_on=("find_customer_by_phone",))
    result, _ = _first_message(repo=broken)
    assert isinstance(result, ConversationError)
    assert "Fake failure" not in result.detail
