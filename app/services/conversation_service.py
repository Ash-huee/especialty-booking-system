"""Conversation state service (Phase 3).

Owns conversation lifecycle only: opening, retrieving, and status changes.
No booking logic, no pricing, no capacity checks, no AI.

Status contract (matches the Phase 1 CHECK constraint exactly):
active, closed, human_handoff. `closed` is terminal — a new message after
closing opens a fresh conversation instead of resurrecting the old one.
"""

from dataclasses import dataclass, field

from app.integrations.booking_repository import RepositoryError
from app.models.booking import ValidationError
from app.models.conversation import (
    CONVERSATION_STATUSES,
    STATUS_ACTIVE,
    SUPPORTED_CHANNELS,
)

# Deterministic transitions. `closed` maps to nothing: it is terminal.
ALLOWED_TRANSITIONS = {
    "active": {"closed", "human_handoff"},
    "human_handoff": {"active", "closed"},
    "closed": set(),
}


@dataclass
class StatusUpdated:
    """A status change was persisted."""

    status: str = "success"
    conversation: dict = field(default_factory=dict)


@dataclass
class StatusValidationFailure:
    """Unknown status or forbidden transition — safe to show the caller."""

    status: str = "validation_error"
    errors: list[ValidationError] = field(default_factory=list)


@dataclass
class StatusNotFound:
    """No conversation with that id exists."""

    status: str = "not_found"
    detail: str = "Conversation not found."


def validate_channel(channel: str) -> list[ValidationError]:
    """Only the local-test channel is implemented in Phase 3."""
    if (channel or "").strip().lower() in SUPPORTED_CHANNELS:
        return []
    return [
        ValidationError(
            field="channel",
            code="UNSUPPORTED_CHANNEL",
            message=(
                f"Channel must be one of: {', '.join(sorted(SUPPORTED_CHANNELS))}."
            ),
        )
    ]


def normalize_channel(channel: str) -> str:
    """Trim and lowercase a channel value (DB stores lowercase)."""
    return (channel or "").strip().lower()


def find_or_open_conversation(
    customer_id: str, channel: str, repository
) -> tuple[dict, bool]:
    """Return (conversation row, created_new), reusing an active thread.

    Channel must already be validated. Raises RepositoryError on failure.
    """
    existing = repository.find_active_conversation(customer_id, channel)
    if existing is not None:
        return existing, False
    return repository.create_conversation(customer_id, channel), True


def get_conversation_detail(
    conversation_id: str, repository
) -> tuple[dict, list[dict]] | None:
    """Return (conversation, messages oldest-first), or None when missing.

    Raises RepositoryError on database failure.
    """
    conversation = repository.get_conversation(conversation_id)
    if conversation is None:
        return None
    messages = repository.list_messages(conversation_id)
    return conversation, messages


def change_conversation_status(
    conversation_id: str, new_status: str, repository
) -> StatusUpdated | StatusValidationFailure | StatusNotFound:
    """Move a conversation to a new status through an allowed transition."""
    target = (new_status or "").strip().lower()
    if target not in CONVERSATION_STATUSES:
        return StatusValidationFailure(
            errors=[
                ValidationError(
                    field="status",
                    code="UNSUPPORTED_CONVERSATION_STATUS",
                    message="Status must be one of: active, closed, human_handoff.",
                )
            ]
        )
    conversation = repository.get_conversation(conversation_id)
    if conversation is None:
        return StatusNotFound()
    current = conversation.get("status", STATUS_ACTIVE)
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        return StatusValidationFailure(
            errors=[
                ValidationError(
                    field="status",
                    code="INVALID_STATUS_TRANSITION",
                    message=(
                        f"Cannot move a conversation from {current} to {target}."
                    ),
                )
            ]
        )
    try:
        updated = repository.update_conversation_status(conversation_id, target)
    except RepositoryError:
        raise
    return StatusUpdated(conversation=updated)
