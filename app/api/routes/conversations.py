"""Conversation routes for local testing (Phase 3).

Thin routes: shape-parse, delegate to the conversation manager/services,
map results to HTTP. No booking logic, no AI, no channel integrations.

* POST /conversations/messages — run the local-test message flow.
* GET /conversations/{conversation_id} — read conversation + ordered history.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.integrations import supabase_client
from app.integrations.booking_repository import RepositoryError
from app.integrations.conversation_repository import ConversationRepository
from app.models.conversation import (
    ConversationError,
    ConversationMessageRequest,
    ConversationMessageResult,
    ConversationValidationFailure,
)
from app.services import conversation_manager, conversation_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversations"])


def get_repository():
    """Build the production repository (monkeypatched in API tests)."""
    client = supabase_client.get_supabase_client()
    if client is None:
        return None
    return ConversationRepository(client)


def _conversation_payload(conversation: dict) -> dict:
    """Expose conversation metadata without database internals."""
    return {
        "id": conversation.get("id"),
        "customer_id": conversation.get("customer_id"),
        "channel": conversation.get("channel"),
        "status": conversation.get("status"),
        "created_at": conversation.get("created_at"),
        "updated_at": conversation.get("updated_at"),
    }


def _message_payload(message: dict) -> dict:
    """Expose one message row in chronological-history shape."""
    return {
        "id": message.get("id"),
        "sender": message.get("sender"),
        "message": message.get("message"),
        "created_at": message.get("created_at"),
    }


@router.post("/conversations/messages")
def post_conversation_message(request: ConversationMessageRequest) -> JSONResponse:
    """Store a local-test customer message (201 / 422 / 503)."""
    repository = get_repository()
    if repository is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "detail": "Conversation service is not configured",
            },
        )
    try:
        result = conversation_manager.handle_customer_message(
            request.customer_name,
            request.customer_phone,
            request.customer_email,
            request.channel,
            request.message,
            repository,
        )
    except Exception:
        logger.exception("Unexpected conversation failure")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "detail": "The conversation service is unavailable.",
            },
        )

    if isinstance(result, ConversationMessageResult):
        return JSONResponse(
            status_code=201,
            content={
                "status": "success",
                "conversation_id": result.conversation_id,
                "customer_id": result.customer_id,
                "message_id": result.message_id,
                "conversation_status": result.conversation_status,
                "created_new_conversation": result.created_new_conversation,
                "created_new_customer": result.created_new_customer,
            },
        )
    if isinstance(result, ConversationValidationFailure):
        return JSONResponse(
            status_code=422,
            content={
                "status": "validation_error",
                "errors": [error.to_dict() for error in result.errors],
            },
        )
    if isinstance(result, ConversationError):
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": result.detail},
        )
    logger.error("Unknown conversation result: %r", type(result))
    return JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "detail": "The conversation service is unavailable.",
        },
    )


@router.get("/conversations/{conversation_id}")
def get_conversation_history(conversation_id: str) -> JSONResponse:
    """Return conversation metadata plus messages oldest-first (200 / 404 / 503)."""
    repository = get_repository()
    if repository is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "detail": "Conversation service is not configured",
            },
        )
    try:
        detail = conversation_service.get_conversation_detail(
            conversation_id, repository
        )
    except RepositoryError:
        logger.exception("Conversation history lookup failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "detail": "The conversation service is unavailable.",
            },
        )
    except Exception:
        logger.exception("Unexpected conversation failure")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "detail": "The conversation service is unavailable.",
            },
        )
    if detail is None:
        return JSONResponse(
            status_code=404,
            content={"status": "not_found", "detail": "Conversation not found."},
        )
    conversation, messages = detail
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "conversation": _conversation_payload(conversation),
            "messages": [_message_payload(message) for message in messages],
        },
    )
