"""Booking request/response data structures (Phase 2).

These Pydantic models check STRUCTURE only (types, shapes).
Business rules (which fields are required for EVENT vs FOOD_ORDER,
guest counts, capacity, pricing) live in `app/services/booking_service.py`
so validation errors use our structured {field, code, message} format.

Deliberately lenient: conditionally-required fields default to None
so the service — not Pydantic — decides what is missing per booking_type.
`event_location` and `special_requests` are `str | None` (not plain `str`)
so an explicit JSON null passes shape validation and reaches business
validation, which still requires `event_location` for EVENT.
"""

from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel


@dataclass
class ValidationError:
    """One structured business-validation failure."""

    field: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Convert to a JSON-safe dict for API responses."""
        return {"field": self.field, "code": self.code, "message": self.message}


class BookingItemInput(BaseModel):
    """One line item in a booking request. Business checks happen in the service."""

    item_name: str = ""
    quantity: int = 1
    unit_price: Decimal = Decimal("0")


class BookingCreateRequest(BaseModel):
    """Structured booking input. Supports both EVENT and FOOD_ORDER."""

    customer_name: str = ""
    customer_phone: str = ""
    customer_email: str = ""
    booking_type: str = ""
    service_type: str = ""
    event_date: date | None = None
    event_time: time | None = None
    # Nullable on purpose: FOOD_ORDER carries no event details, while the
    # service still rejects null/blank locations for EVENT bookings.
    event_location: str | None = None
    guest_count: int | None = None
    package_id: str | None = None
    estimated_price: Decimal | None = None
    # Nullable on purpose: "no special requests" is valid for both types.
    special_requests: str | None = None
    booking_items: list[BookingItemInput] = []
