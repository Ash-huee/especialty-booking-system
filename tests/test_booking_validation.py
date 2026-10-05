"""Unit tests for deterministic booking validation (Phase 2).

Covers customer, EVENT, FOOD_ORDER, service-type, and package rules.
Uses the fake repository — no live database.
"""

from tests.fakes import (
    ACTIVE_PACKAGE_ID,
    INACTIVE_PACKAGE_ID,
    FakeBookingRepository,
    active_package,
    make_food_order_request,
    make_request,
)

from app.services import booking_service
from app.services.booking_service import BookingValidationFailure


def codes(result) -> list[str]:
    """Extract error codes from a validation failure."""
    assert isinstance(result, BookingValidationFailure)
    return [error.code for error in result.errors]


def test_missing_customer_name() -> None:
    """Blank customer name is rejected."""
    result = booking_service.create_booking(
        make_request(customer_name="   "), FakeBookingRepository()
    )
    assert "REQUIRED_CUSTOMER_NAME" in codes(result)


def test_missing_customer_phone() -> None:
    """Blank customer phone is rejected."""
    result = booking_service.create_booking(
        make_request(customer_phone="  "), FakeBookingRepository()
    )
    assert "REQUIRED_CUSTOMER_PHONE" in codes(result)


def test_invalid_email_rejected_blank_email_ok() -> None:
    """Bad email fails; empty email (optional) passes to later checks."""
    bad = booking_service.create_booking(
        make_food_order_request(customer_email="not-an-email"),
        FakeBookingRepository(),
    )
    assert "INVALID_EMAIL" in codes(bad)

    ok = booking_service.create_booking(
        make_food_order_request(customer_email=""),
        FakeBookingRepository(),
    )
    assert not isinstance(ok, BookingValidationFailure)


def test_event_missing_date_time_location_guests() -> None:
    """Each missing EVENT field produces its own error code."""
    repo = FakeBookingRepository()
    assert "REQUIRED_EVENT_DATE" in codes(
        booking_service.create_booking(make_request(event_date=None), repo)
    )
    assert "REQUIRED_EVENT_TIME" in codes(
        booking_service.create_booking(make_request(event_time=None), repo)
    )
    assert "REQUIRED_EVENT_LOCATION" in codes(
        booking_service.create_booking(make_request(event_location="  "), repo)
    )
    assert "REQUIRED_GUEST_COUNT" in codes(
        booking_service.create_booking(make_request(guest_count=None), repo)
    )


def test_event_invalid_guest_count() -> None:
    """Zero or negative guest counts are rejected."""
    for bad_count in (0, -3):
        result = booking_service.create_booking(
            make_request(guest_count=bad_count), FakeBookingRepository()
        )
        assert "INVALID_GUEST_COUNT" in codes(result)


def test_unsupported_booking_and_service_types() -> None:
    """Unknown types are rejected, never silently converted."""
    result = booking_service.create_booking(
        make_request(booking_type="PARTY"), FakeBookingRepository()
    )
    assert "UNSUPPORTED_BOOKING_TYPE" in codes(result)

    result = booking_service.create_booking(
        make_request(service_type="luxury_helicopter"), FakeBookingRepository()
    )
    assert "UNSUPPORTED_SERVICE_TYPE" in codes(result)
    # The bad value must not have been stored anywhere.
    assert result.errors[0].field == "service_type"


def test_food_order_needs_items() -> None:
    """FOOD_ORDER without items is rejected."""
    result = booking_service.create_booking(
        make_food_order_request(booking_items=[]), FakeBookingRepository()
    )
    assert "REQUIRED_BOOKING_ITEMS" in codes(result)


def test_food_order_invalid_quantity_and_name() -> None:
    """Zero quantity and blank item names are rejected."""
    result = booking_service.create_booking(
        make_food_order_request(
            booking_items=[{"item_name": "Tray", "quantity": 0, "unit_price": "5.00"}]
        ),
        FakeBookingRepository(),
    )
    assert "INVALID_ITEM_QUANTITY" in codes(result)

    result = booking_service.create_booking(
        make_food_order_request(
            booking_items=[{"item_name": "   ", "quantity": 1, "unit_price": "5.00"}]
        ),
        FakeBookingRepository(),
    )
    assert "INVALID_ITEM_NAME" in codes(result)


def test_negative_prices_rejected() -> None:
    """Negative estimated_price and unit_price are rejected."""
    result = booking_service.create_booking(
        make_food_order_request(estimated_price="-1.00"), FakeBookingRepository()
    )
    assert "INVALID_PRICE" in codes(result)

    result = booking_service.create_booking(
        make_food_order_request(
            booking_items=[{"item_name": "Tray", "quantity": 1, "unit_price": "-2.00"}]
        ),
        FakeBookingRepository(),
    )
    assert "INVALID_ITEM_PRICE" in codes(result)


def test_package_not_found_inactive_or_malformed() -> None:
    """Unknown, inactive, or malformed package ids are validation errors."""
    repo = FakeBookingRepository(
        packages={
            ACTIVE_PACKAGE_ID: active_package(),
            INACTIVE_PACKAGE_ID: {**active_package(), "id": INACTIVE_PACKAGE_ID, "is_active": False},
        }
    )
    missing = booking_service.create_booking(
        make_request(package_id="33333333-3333-3333-3333-333333333333"), repo
    )
    assert "PACKAGE_NOT_FOUND" in codes(missing)

    inactive = booking_service.create_booking(
        make_request(package_id=INACTIVE_PACKAGE_ID), repo
    )
    assert "PACKAGE_INACTIVE" in codes(inactive)

    malformed = booking_service.create_booking(make_request(package_id="not-a-uuid"), repo)
    assert "PACKAGE_NOT_FOUND" in codes(malformed)


def test_food_order_ignores_event_fields() -> None:
    """FOOD_ORDER with no event date/time/location is valid."""
    result = booking_service.create_booking(
        make_food_order_request(), FakeBookingRepository()
    )
    assert isinstance(result, booking_service.BookingSuccess)
