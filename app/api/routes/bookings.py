"""Booking creation route (Phase 2).

Thin route: parses the request shape, delegates every business decision
to `booking_service.create_booking`, then maps the result to HTTP.
No prices, capacity checks, or validation rules live here.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.integrations import supabase_client
from app.integrations.booking_repository import SupabaseBookingRepository
from app.models.booking import BookingCreateRequest
from app.services import booking_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bookings"])


def get_repository():
    """Build the production repository (monkeypatched in API tests)."""
    client = supabase_client.get_supabase_client()
    if client is None:
        return None
    return SupabaseBookingRepository(client)


@router.post("/bookings")
def create_booking_endpoint(request: BookingCreateRequest) -> JSONResponse:
    """Create a booking deterministically (201 / 422 / 409 / 202 / 503)."""
    repository = get_repository()
    if repository is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "detail": "Booking service is not configured",
            },
        )
    try:
        result = booking_service.create_booking(request, repository)
    except Exception:
        logger.exception("Unexpected booking failure")
        return JSONResponse(
            status_code=202,
            content={
                "status": "human_handoff",
                "booking_status": "HUMAN_HANDOFF",
                "message": "This request needs staff review before it can proceed.",
            },
        )

    if isinstance(result, booking_service.BookingSuccess):
        return JSONResponse(
            status_code=201,
            content={
                "status": "success",
                "booking_id": result.booking_id,
                "booking_status": result.booking_status,
                "estimated_price": result.estimated_price,
            },
        )
    if isinstance(result, booking_service.BookingValidationFailure):
        errors = [error.to_dict() for error in result.errors]
        # Capacity conflicts get 409 so callers can distinguish "full date"
        # from other validation problems; the body shape stays the same.
        status_code = 422
        if any(error.code == "EVENT_CAPACITY_REACHED" for error in result.errors):
            status_code = 409
        return JSONResponse(
            status_code=status_code,
            content={"status": "validation_error", "errors": errors},
        )
    return JSONResponse(
        status_code=202,
        content={
            "status": "human_handoff",
            "booking_status": result.booking_status,
            "message": result.message,
            **({"booking_id": result.booking_id} if result.booking_id else {}),
        },
    )
