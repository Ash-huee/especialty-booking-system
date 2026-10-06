"""Message service (Phase 3).

Appends messages and reads history in chronological order. Message rows
are append-only (the table has no updated_at) — this service never edits
or deletes. No Gemini, no booking decisions.
"""

from app.models.booking import ValidationError
from app.models.conversation import SUPPORTED_SENDERS, SENDER_CUSTOMER


def validate_message_text(text: str) -> list[ValidationError]:
    """A message must contain non-blank content."""
    if (text or "").strip():
        return []
    return [
        ValidationError(
            field="message",
            code="REQUIRED_MESSAGE",
            message="Message content is required.",
        )
    ]


def store_message(
    conversation_id: str, sender: str, text: str, repository
) -> dict:
    """Append one message row. Raises RepositoryError on database failure."""
    if sender not in SUPPORTED_SENDERS:
        raise ValueError(
            f"Unsupported sender: {sender!r}. "
            "Phase 3 produces customer, staff, or system messages only; "
            "'assistant' is reserved for future Gemini replies."
        )
    return repository.create_message(conversation_id, sender, text.strip())


def store_customer_message(
    conversation_id: str, text: str, repository
) -> dict:
    """Append an incoming customer message (the Phase 3 local-test path)."""
    return store_message(conversation_id, SENDER_CUSTOMER, text, repository)


def get_history(conversation_id: str, repository) -> list[dict]:
    """Return a conversation's messages, oldest first."""
    return repository.list_messages(conversation_id)
