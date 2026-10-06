"""Conversation manager: the Phase 3 local-test message flow (no AI).

Steps, in order:
1. Normalize and validate customer identity (shared Phase 2 rules).
2. Validate channel (local_test only) and message content.
3. Find or create the customer (shared matching, no AI, no fuzz).
4. Reuse the customer's active conversation on that channel, else open one.
5. Store the incoming customer message.
6. Return structured information about what happened.

The manager never calls Gemini (it does not exist yet), never creates
bookings, and never infers intent. It only prepares persisted context
that future AI and channel integrations will build on.
"""

from app.integrations.booking_repository import RepositoryError
from app.models.booking import ValidationError
from app.models.conversation import (
    ConversationError,
    ConversationMessageResult,
    ConversationValidationFailure,
)
from app.models.customer import normalize_customer_data, validate_customer
from app.services import conversation_service, message_service
from app.services.customer_service import find_or_create_customer


def handle_customer_message(
    customer_name: str,
    customer_phone: str,
    customer_email: str,
    channel: str,
    message_text: str,
    repository,
) -> (
    ConversationMessageResult | ConversationValidationFailure | ConversationError
):
    """Run the local-test flow: customer → conversation → stored message.

    `repository` is any object with the ConversationRepository methods
    (real one in production, a fake in tests).
    """
    # -- 1-2. validate everything that needs no database ----------------------
    customer = normalize_customer_data(customer_name, customer_phone, customer_email)
    errors: list[ValidationError] = validate_customer(customer)
    errors.extend(conversation_service.validate_channel(channel))
    errors.extend(message_service.validate_message_text(message_text))
    if errors:
        return ConversationValidationFailure(errors=errors)

    clean_channel = conversation_service.normalize_channel(channel)

    # -- 3-5. persist in dependency order --------------------------------------
    try:
        customer_row, created_new_customer = find_or_create_customer(
            customer, repository
        )
        conversation, created_new = (
            conversation_service.find_or_open_conversation(
                customer_row["id"], clean_channel, repository
            )
        )
        stored = message_service.store_customer_message(
            conversation["id"], message_text, repository
        )
    except RepositoryError:
        return ConversationError()

    return ConversationMessageResult(
        conversation_id=conversation["id"],
        customer_id=customer_row["id"],
        message_id=stored["id"],
        conversation_status=conversation.get("status", "active"),
        created_new_conversation=created_new,
        created_new_customer=created_new_customer,
    )
