"""API tests for the conversation endpoints (Phase 3).

Routes stay thin: HTTP mapping is tested here with a fake repository,
so no live database is needed.
"""

from fastapi.testclient import TestClient

from app.api.routes import conversations
from app.main import app
from tests.conversation_fakes import FakeConversationRepository

client = TestClient(app)


def _message_payload(**overrides) -> dict:
    base = {
        "customer_name": "Ana Lopez",
        "customer_phone": "+10000000001",
        "channel": "local_test",
        "message": "Hello, I need catering.",
    }
    base.update(overrides)
    return base


def test_post_message_success_returns_201(monkeypatch) -> None:
    """Valid local-test message → 201 with conversation and message ids."""
    monkeypatch.setattr(
        conversations, "get_repository", lambda: FakeConversationRepository()
    )

    response = client.post("/conversations/messages", json=_message_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["conversation_id"]
    assert body["customer_id"]
    assert body["message_id"]
    assert body["conversation_status"] == "active"
    assert body["created_new_conversation"] is True
    assert "customer_phone" not in body  # No unnecessary personal data echoed.


def test_post_message_validation_error_returns_422(monkeypatch) -> None:
    """Blank message → 422 with structured {field, code, message}."""
    monkeypatch.setattr(
        conversations, "get_repository", lambda: FakeConversationRepository()
    )

    response = client.post("/conversations/messages", json=_message_payload(message="  "))

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "validation_error"
    assert body["errors"][0] == {
        "field": "message",
        "code": "REQUIRED_MESSAGE",
        "message": "Message content is required.",
    }


def test_post_message_rejects_facebook_channel(monkeypatch) -> None:
    """Messenger channel is not implemented → 422, nothing stored."""
    repo = FakeConversationRepository()
    monkeypatch.setattr(conversations, "get_repository", lambda: repo)

    response = client.post(
        "/conversations/messages", json=_message_payload(channel="facebook")
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "UNSUPPORTED_CHANNEL"
    assert repo.customers == [] and repo.conversations == []


def test_post_message_unconfigured_returns_503(monkeypatch) -> None:
    """No Supabase credentials → 503 without leaking anything."""
    monkeypatch.setattr(conversations, "get_repository", lambda: None)

    response = client.post("/conversations/messages", json=_message_payload())

    assert response.status_code == 503
    assert response.json()["status"] == "error"


def test_post_message_db_failure_returns_503(monkeypatch) -> None:
    """Repository failure → 503 with a generic message (no raw exception)."""
    monkeypatch.setattr(
        conversations,
        "get_repository",
        lambda: FakeConversationRepository(fail_on=("create_conversation",)),
    )

    response = client.post("/conversations/messages", json=_message_payload())

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert "Fake failure" not in response.text


def test_get_history_returns_ordered_messages(monkeypatch) -> None:
    """POST twice, then GET history shows metadata + oldest-first messages."""
    repo = FakeConversationRepository()
    monkeypatch.setattr(conversations, "get_repository", lambda: repo)

    first = client.post("/conversations/messages", json=_message_payload()).json()
    client.post(
        "/conversations/messages", json=_message_payload(message="Second message.")
    ).json()

    response = client.get(f"/conversations/{first['conversation_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["conversation"]["id"] == first["conversation_id"]
    assert body["conversation"]["customer_id"] == first["customer_id"]
    assert body["conversation"]["channel"] == "local_test"
    assert body["conversation"]["status"] == "active"
    assert [message["message"] for message in body["messages"]] == [
        "Hello, I need catering.",
        "Second message.",
    ]
    assert [message["sender"] for message in body["messages"]] == [
        "customer",
        "customer",
    ]


def test_get_history_missing_returns_404(monkeypatch) -> None:
    """Unknown conversation id → 404 not_found."""
    monkeypatch.setattr(
        conversations, "get_repository", lambda: FakeConversationRepository()
    )

    response = client.get("/conversations/does-not-exist")

    assert response.status_code == 404
    assert response.json()["status"] == "not_found"
