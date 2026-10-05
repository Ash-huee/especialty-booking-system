"""Deterministic booking engine (Phase 2).

No AI here: every decision below is a plain Python rule so results are
predictable and testable. AI (Phase 3+) will only extract structured
data; THIS module decides whether a booking is valid.

Order of operations (partial-write safety):
  1. Validate everything that needs no database (customer, types, fields).
  2. Validate against the database (package, capacity, pricing inputs).
  3. Only then write: customer -> booking -> booking_items.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.integrations.booking_repository import RepositoryError
from app.models.booking import BookingCreateRequest, ValidationError
from app.models.customer import normalize_customer_data, validate_customer
from app.services import pricing_service

SUPPORTED_BOOKING_TYPES = {"EVENT", "FOOD_ORDER"}
SUPPORTED_SERVICE_TYPES = {
    "catering",
    "food_trays",
    "party_package",
    "individual_food_order",
}


@dataclass
class BookingSuccess:
    """A valid booking was stored. New bookings always start as PENDING."""

    status: str = "success"
    booking_id: str = ""
    booking_status: str = "PENDING"
    estimated_price: str | None = None


@dataclass
class BookingValidationFailure:
    """Deterministic rule rejection — safe to show the caller."""

    status: str = "validation_error"
    errors: list[ValidationError] = field(default_factory=list)


@dataclass
class BookingHandoff:
    """The engine cannot safely proceed — a human must take over."""

    status: str = "human_handoff"
    booking_status: str = "HUMAN_HANDOFF"
    message: str = "This request needs staff review before it can proceed."
    booking_id: str | None = None
    errors: list[ValidationError] = field(default_factory=list)


BookingResult = BookingSuccess | BookingValidationFailure | BookingHandoff


def _is_valid_uuid(value: str) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _validate_item(item, index: int) -> list[ValidationError]:
    """Validate one booking item (used for FOOD_ORDER and optional EVENT items)."""
    errors: list[ValidationError] = []
    name = (item.item_name or "").strip()
    if not name:
        errors.append(
            ValidationError(
                field=f"booking_items[{index}].item_name",
                code="INVALID_ITEM_NAME",
                message="Item name cannot be blank.",
            )
        )
    try:
        quantity = int(item.quantity)
    except (TypeError, ValueError):
        quantity = 0
    if quantity <= 0:
        errors.append(
            ValidationError(
                field=f"booking_items[{index}].quantity",
                code="INVALID_ITEM_QUANTITY",
                message="Item quantity must be greater than zero.",
            )
        )
    try:
        unit_price = pricing_service.to_decimal(item.unit_price)
    except ValueError:
        unit_price = Decimal("-1")
    if unit_price < 0:
        errors.append(
            ValidationError(
                field=f"booking_items[{index}].unit_price",
                code="INVALID_ITEM_PRICE",
                message="Item price cannot be negative.",
            )
        )
    return errors


def create_booking(
    request: BookingCreateRequest, repository
) -> BookingResult:
    """Validate a booking request and store it when valid.

    `repository` is any object with the SupabaseBookingRepository methods
    (real one in production, a fake in unit tests).
    """
    # -- 1. customer (no database yet) ------------------------------------
    customer = normalize_customer_data(
        request.customer_name, request.customer_phone, request.customer_email
    )
    errors: list[ValidationError] = validate_customer(customer)

    # -- 2. booking_type / service_type ------------------------------------
    booking_type = (request.booking_type or "").strip().upper()
    service_type = (request.service_type or "").strip().lower()
    if booking_type not in SUPPORTED_BOOKING_TYPES:
        errors.append(
            ValidationError(
                field="booking_type",
                code="UNSUPPORTED_BOOKING_TYPE",
                message="Booking type must be EVENT or FOOD_ORDER.",
            )
        )
    if not service_type or service_type not in SUPPORTED_SERVICE_TYPES:
        errors.append(
            ValidationError(
                field="service_type",
                code="UNSUPPORTED_SERVICE_TYPE",
                message=(
                    "Service type must be one of: catering, food_trays, "
                    "party_package, individual_food_order."
                ),
            )
        )

    # -- 3. supplied estimated_price must never be negative -----------------
    if request.estimated_price is not None:
        try:
            supplied = pricing_service.to_decimal(request.estimated_price)
        except ValueError:
            supplied = Decimal("-1")
        if supplied < 0:
            errors.append(
                ValidationError(
                    field="estimated_price",
                    code="INVALID_PRICE",
                    message="Estimated price cannot be negative.",
                )
            )

    # -- 4. type-specific required fields ------------------------------------
    if booking_type == "EVENT":
        if request.event_date is None:
            errors.append(
                ValidationError(
                    field="event_date",
                    code="REQUIRED_EVENT_DATE",
                    message="Event date is required for EVENT bookings.",
                )
            )
        if request.event_time is None:
            errors.append(
                ValidationError(
                    field="event_time",
                    code="REQUIRED_EVENT_TIME",
                    message="Event time is required for EVENT bookings.",
                )
            )
        if not (request.event_location or "").strip():
            errors.append(
                ValidationError(
                    field="event_location",
                    code="REQUIRED_EVENT_LOCATION",
                    message="Event location is required for EVENT bookings.",
                )
            )
        if request.guest_count is None:
            errors.append(
                ValidationError(
                    field="guest_count",
                    code="REQUIRED_GUEST_COUNT",
                    message="Guest count is required for EVENT bookings.",
                )
            )
        elif request.guest_count <= 0:
            errors.append(
                ValidationError(
                    field="guest_count",
                    code="INVALID_GUEST_COUNT",
                    message="Guest count must be greater than zero.",
                )
            )
        # EVENT items are optional, but validated when present.
        for index, item in enumerate(request.booking_items or []):
            errors.extend(_validate_item(item, index))
    elif booking_type == "FOOD_ORDER":
        if not request.booking_items:
            errors.append(
                ValidationError(
                    field="booking_items",
                    code="REQUIRED_BOOKING_ITEMS",
                    message="A food order needs at least one booking item.",
                )
            )
        for index, item in enumerate(request.booking_items or []):
            errors.extend(_validate_item(item, index))

    if errors:
        return BookingValidationFailure(errors=errors)

    # -- 5. package lookup (database) ----------------------------------------
    # A package_id that is supplied but missing/inactive is the CALLER's
    # mistake -> validation error. A database failure here is OUR problem
    # -> human handoff (unexpected database state).
    package = None
    raw_package_id = (request.package_id or "").strip()
    if raw_package_id:
        if not _is_valid_uuid(raw_package_id):
            return BookingValidationFailure(
                errors=[
                    ValidationError(
                        field="package_id",
                        code="PACKAGE_NOT_FOUND",
                        message="The selected package could not be found.",
                    )
                ]
            )
        try:
            package = repository.get_package(raw_package_id)
        except RepositoryError:
            return BookingHandoff(
                message="We could not verify the package. Staff will review this request."
            )
        if package is None:
            return BookingValidationFailure(
                errors=[
                    ValidationError(
                        field="package_id",
                        code="PACKAGE_NOT_FOUND",
                        message="The selected package could not be found.",
                    )
                ]
            )
        if not package.get("is_active", False):
            return BookingValidationFailure(
                errors=[
                    ValidationError(
                        field="package_id",
                        code="PACKAGE_INACTIVE",
                        message="The selected package is no longer available.",
                    )
                ]
            )

    # -- 6. capacity (EVENT only, limit comes from the database) -------------
    if booking_type == "EVENT":
        try:
            max_events = repository.get_max_events_per_day()
            active_count = repository.count_active_events(request.event_date)
        except RepositoryError:
            return BookingHandoff(
                message="We could not check availability. Staff will review this request."
            )
        if active_count >= max_events:
            return BookingValidationFailure(
                errors=[
                    ValidationError(
                        field="event_date",
                        code="EVENT_CAPACITY_REACHED",
                        message="Especialty has reached its maximum number of events for this date.",
                    )
                ]
            )

    # -- 7. deterministic pricing ----------------------------------------------
    estimated: Decimal | None = None
    if booking_type == "EVENT" and package is not None:
        estimated = pricing_service.calculate_event_price(
            request.guest_count or 0,
            pricing_service.to_decimal(package["price_per_person"]),
        )
    elif booking_type == "FOOD_ORDER":
        estimated = pricing_service.calculate_food_order_total(request.booking_items)
    estimated_str = str(estimated) if estimated is not None else None

    # -- 8. customer matching (deterministic, no AI) ------------------------------
    # Rule: exact phone match wins; otherwise exact email match; otherwise
    # create a new customer. Simple, explainable, no fuzzy matching.
    try:
        existing = repository.find_customer_by_phone(customer.phone)
        if existing is None and customer.email:
            existing = repository.find_customer_by_email(customer.email)
        if existing is None:
            existing = repository.create_customer(
                customer.name, customer.phone, customer.email
            )
        customer_id = existing.get("id")
        if not customer_id:
            raise RepositoryError("Customer record has no id")
    except RepositoryError:
        return BookingHandoff(
            message="We could not save the customer record. Staff will review this request."
        )

    # -- 9. store the booking (always PENDING, never auto-CONFIRMED) --------------
    payload = {
        "customer_id": customer_id,
        "booking_type": booking_type,
        "service_type": service_type,
        "event_date": request.event_date.isoformat() if request.event_date else None,
        "event_time": request.event_time.isoformat() if request.event_time else None,
        "event_location": (request.event_location or "").strip() or None,
        "guest_count": request.guest_count,
        "package_id": raw_package_id or None,
        "estimated_price": estimated_str,
        "status": "PENDING",
        "payment_status": "UNPAID",
        "special_requests": (request.special_requests or "").strip() or None,
    }
    try:
        booking_row = repository.create_booking(payload)
        booking_id = booking_row.get("id")
        if not booking_id:
            raise RepositoryError("Booking record has no id")
    except RepositoryError:
        return BookingHandoff(
            message="We could not save the booking. Staff will review this request."
        )

    # -- 10. store items (when present) -------------------------------------------
    if request.booking_items:
        item_rows = []
        for item in request.booking_items:
            quantity = int(item.quantity)
            unit = pricing_service.money(pricing_service.to_decimal(item.unit_price))
            subtotal = pricing_service.money(
                pricing_service.to_decimal(quantity) * unit
            )
            item_rows.append(
                {
                    "item_name": (item.item_name or "").strip(),
                    "quantity": quantity,
                    "unit_price": str(unit),
                    "subtotal": str(subtotal),
                }
            )
        try:
            repository.create_booking_items(booking_id, item_rows)
        except RepositoryError:
            # LIMITATION (documented): no multi-table transaction through the
            # Supabase REST client, so the booking row above already exists.
            # Return a handoff WITH the booking_id so staff can reconcile
            # instead of leaving a silent orphan.
            return BookingHandoff(
                message="The booking was saved but its items were not. Staff will review it.",
                booking_id=booking_id,
            )

    return BookingSuccess(
        booking_id=booking_id, booking_status="PENDING", estimated_price=estimated_str
    )
