"""Unit tests for customer matching, status, and human handoff (Phase 2)."""

from tests.fakes import (
    ACTIVE_PACKAGE_ID,
    FakeBookingRepository,
    active_package,
    make_food_order_request,
    make_request,
)

from app.services import booking_service
from app.services.booking_service import (
    BookingHandoff,
    BookingSuccess,
    BookingValidationFailure,
)


def test_valid_new_booking_starts_pending() -> None:
    """Success stores PENDING (never auto-CONFIRMED) with a Decimal price string."""
    repo = FakeBookingRepository(
        packages={ACTIVE_PACKAGE_ID: active_package("25.50")}
    )
    result = booking_service.create_booking(
        make_request(guest_count=4, package_id=ACTIVE_PACKAGE_ID), repo
    )
    assert isinstance(result, BookingSuccess)
    assert result.booking_status == "PENDING"
    assert result.estimated_price == "102.00"  # 4 x 25.50, Decimal-safe
    assert repo.created_bookings[0]["status"] == "PENDING"


def test_food_order_price_is_item_sum() -> None:
    """FOOD_ORDER price = sum of lines, stored as a string for NUMERIC."""
    repo = FakeBookingRepository()
    result = booking_service.create_booking(
        make_food_order_request(
            booking_items=[
                {"item_name": "A", "quantity": 2, "unit_price": "10.00"},
                {"item_name": "B", "quantity": 1, "unit_price": "3.50"},
            ]
        ),
        repo,
    )
    assert isinstance(result, BookingSuccess)
    assert result.estimated_price == "23.50"


def test_invalid_booking_creates_nothing_and_is_not_confirmed() -> None:
    """A validation failure stores no customer, booking, or items."""
    repo = FakeBookingRepository()
    result = booking_service.create_booking(make_request(guest_count=0), repo)
    assert isinstance(result, BookingValidationFailure)
    assert repo.created_bookings == []
    assert repo.created_customers == []
    assert repo.created_items == []


def test_existing_customer_reused_by_phone() -> None:
    """An exact phone match reuses the customer (no duplicate created)."""
    repo = FakeBookingRepository(
        existing_customers=[
            {"id": "cust-1", "name": "Ana", "phone": "+10000000001", "email": None}
        ]
    )
    result = booking_service.create_booking(make_food_order_request(), repo)
    assert isinstance(result, BookingSuccess)
    assert repo.created_customers == []
    assert repo.created_bookings[0]["customer_id"] == "cust-1"


def test_email_fallback_when_phone_unknown() -> None:
    """Unknown phone + known email reuses the email-matched customer."""
    repo = FakeBookingRepository(
        existing_customers=[
            {"id": "cust-9", "name": "Ana", "phone": "+1999", "email": "ana@example.com"}
        ]
    )
    result = booking_service.create_booking(
        make_food_order_request(
            customer_phone="+10000000001", customer_email="ana@example.com"
        ),
        repo,
    )
    assert isinstance(result, BookingSuccess)
    assert repo.created_customers == []
    assert repo.created_bookings[0]["customer_id"] == "cust-9"


def test_new_customer_created_when_no_match() -> None:
    """Unknown phone and email create exactly one customer row."""
    repo = FakeBookingRepository()
    result = booking_service.create_booking(make_food_order_request(), repo)
    assert isinstance(result, BookingSuccess)
    assert len(repo.created_customers) == 1
    assert (
        repo.created_bookings[0]["customer_id"] == repo.created_customers[0]["id"]
    )


def test_whitespace_is_trimmed() -> None:
    """Padded name/phone are accepted (trimmed), not rejected."""
    repo = FakeBookingRepository()
    result = booking_service.create_booking(
        make_food_order_request(customer_name="  Ana  ", customer_phone="  +10000000001  "),
        repo,
    )
    assert isinstance(result, BookingSuccess)
    assert repo.created_customers[0]["name"] == "Ana"
    assert repo.created_customers[0]["phone"] == "+10000000001"


def test_database_failure_becomes_handoff() -> None:
    """Unexpected DB states escalate instead of guessing."""
    capacity_broken = FakeBookingRepository(fail_on=("get_max_events_per_day",))
    result = booking_service.create_booking(make_request(), capacity_broken)
    assert isinstance(result, BookingHandoff)
    assert result.booking_status == "HUMAN_HANDOFF"

    save_broken = FakeBookingRepository(fail_on=("create_booking",))
    result = booking_service.create_booking(make_food_order_request(), save_broken)
    assert isinstance(result, BookingHandoff)


def test_items_failure_keeps_booking_id_for_staff() -> None:
    """Items failing after the booking row exists still returns its id."""
    repo = FakeBookingRepository(fail_on=("create_booking_items",))
    result = booking_service.create_booking(make_food_order_request(), repo)
    assert isinstance(result, BookingHandoff)
    assert result.booking_id is not None
    assert len(repo.created_bookings) == 1  # Documented partial-write case.
