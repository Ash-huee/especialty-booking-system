"""Conversation request/response data structures (Phase 3).

Database contract (from `001_initial_schema.sql`, preserved as-is):
* channel is one of 'facebook', 'website', 'sms', 'local_test'.
* conversation status is one of 'active', 'closed', 'human_handoff'.
* message sender is one of 'customer', 'assistant', 'staff', 'system'.

Phase 3 implements the `local_test` channel only; the other channels and
the 'assistant' sender are reserved for future phases (Messenger, Gemini).
The task-level names ACTIVE/CLOSED/HUMAN_HANDOFF and CUSTOMER/SYSTEM/STAFF
map to these lowercase database values.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel

from app.models.booking import ValidationError

# Conversation statuses exactly as stored in the database.
STATUS_ACTIVE = "active"
STATUS_CLOSED = "closed"
STATUS_HUMAN_HANDOFF = "human_handoff"
CONVERSATION_STATUSES = {STATUS_ACTIVE, STATUS_CLOSED, STATUS_HUMAN_HANDOFF}

# Only the local-test channel is implemented in Phase 3.
CHANNEL_LOCAL_TEST = "local_test"
SUPPORTED_CHANNELS = {CHANNEL_LOCAL_TEST}

# Senders used in Phase 3. 'assistant' exists in the schema for future
# Gemini-generated replies and is intentionally not produced here.
SENDER_CUSTOMER = "customer"
SENDER_STAFF = "staff"
SENDER_SYSTEM = "system"
SUPPORTED_SENDERS = {SENDER_CUSTOMER, SENDER_STAFF, SENDER_SYSTEM}


class ConversationMessageRequest(BaseModel):
    """Incoming local-test customer message (shape only, no decisions)."""

    customer_name: str = ""
    customer_phone: str = ""
    customer_email: str = ""
    channel: str = CHANNEL_LOCAL_TEST
    message: str = ""


@dataclass
class ConversationMessageResult:
    """Outcome of the local-test message flow."""

    status: str = "success"
    conversation_id: str = ""
    customer_id: str = ""
    message_id: str = ""
    conversation_status: str = STATUS_ACTIVE
    created_new_conversation: bool = False
    created_new_customer: bool = False


@dataclass
class ConversationValidationFailure:
    """Invalid request — safe to show the caller."""

    status: str = "validation_error"
    errors: list[ValidationError] = field(default_factory=list)


@dataclass
class ConversationError:
    """Database or configuration failure — never leaks internals."""

    status: str = "error"
    detail: str = "The conversation service is unavailable."
