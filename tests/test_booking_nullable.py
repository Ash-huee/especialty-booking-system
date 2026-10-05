"""Nullability tests for the booking request model (Phase 2 fix).

Rule under test: Pydantic accepts JSON null for legitimately inapplicable
fields (`event_location`, `special_requests`, plus the already-nullable
`event_date`/`event_time`/`guest_count`/`package_id`); the booking service
still enforces EVENT requirements. No live database needed.
"""

from fastapi.testclient import TestClient

from app.api.routes import bookings
from app.main import app
from app.models.booking import BookingCreateRequest
from app.services import booking_service
from app.services.booking_service import BookingSuccess, BookingValidationFailure
from tests.fakes import FakeBookingRepository, make_food_order_request, make_request

client = TestClient(app)


def test_event_with_required_event_fields_succeeds() -> None:
    """EVENT with all event fields present passes business validation."""
    result = booking_service.create_booking(make_request(), FakeBookingRepository())
    assert isinstance(result, BookingSuccess)
    assert result.booking_status == "PENDING"


def test_event_with_null_location_rejected() -> None:
    """EVENT with event_location=null fails with REQUIRED_EVENT_LOCATION."""
    result = booking_service.create_booking(
        make_request(event_location=None), FakeBookingRepository()
    )
    assert isinstance(result, BookingValidationFailure)
    assert result.errors[0].code == "REQUIRED_EVENT_LOCATION"
    assert result.errors[0].field == "event_location"


def test_food_order_null_location_reaches_business_validation() -> None:
    """FOOD_ORDER with event_location=null constructs and validates fine."""
    request = make_food_order_request(event_location=None)
    assert request.event_location is None
    result = booking_service.create_booking(request, FakeBookingRepository())
    assert isinstance(result, BookingSuccess)


def test_food_order_null_date_accepted() -> None:
    """FOOD_ORDER with event_date=null is accepted."""
    request = make_food_order_request(event_date=None)
    assert request.event_date is None
    result = booking_service.create_booking(request, FakeBookingRepository())
    assert isinstance(result, BookingSuccess)


def test_food_order_null_time_accepted() -> None:
    """FOOD_ORDER with event_time=null is accepted."""
    request = make_food_order_request(event_time=None)
    assert request.event_time is None
    result = booking_service.create_booking(request, FakeBookingRepository())
    assert isinstance(result, BookingSuccess)


def test_food_order_null_guest_count_accepted() -> None:
    """FOOD_ORDER with guest_count=null is accepted."""
    request = make_food_order_request(guest_count=None)
    assert request.guest_count is None
    result = booking_service.create_booking(request, FakeBookingRepository())
    assert isinstance(result, BookingSuccess)


def test_food_order_null_package_accepted() -> None:
    """FOOD_ORDER with package_id=null is accepted."""
    request = make_food_order_request(package_id=None)
    assert request.package_id is None
    result = booking_service.create_booking(request, FakeBookingRepository())
    assert isinstance(result, BookingSuccess)


def test_special_requests_null_accepted() -> None:
    """special_requests=null is accepted for both booking types."""
    event_request = BookingCreateRequest(
        **{**make_request().model_dump(), "special_requests": None}
    )
    assert event_request.special_requests is None
    assert isinstance(
        booking_service.create_booking(event_request, FakeBookingRepository()),
        BookingSuccess,
    )

    food_request = make_food_order_request(special_requests=None)
    assert food_request.special_requests is None
    result = booking_service.create_booking(food_request, FakeBookingRepository())
    assert isinstance(result, BookingSuccess)


def test_existing_invalid_requests_still_fail() -> None:
    """Loosening nullability did not weaken business validation."""
    repo = FakeBookingRepository()
    bad_guests = booking_service.create_booking(make_request(guest_count=0), repo)
    assert isinstance(bad_guests, BookingValidationFailure)
    assert bad_guests.errors[0].code == "INVALID_GUEST_COUNT"

    no_items = booking_service.create_booking(
        make_food_order_request(booking_items=[]), FakeBookingRepository()
    )
    assert isinstance(no_items, BookingValidationFailure)
    assert no_items.errors[0].code == "REQUIRED_BOOKING_ITEMS"

    no_name = booking_service.create_booking(
        make_food_order_request(customer_name="  "), FakeBookingRepository()
    )
    assert isinstance(no_name, BookingValidationFailure)
    assert no_name.errors[0].code == "REQUIRED_CUSTOMER_NAME"


def test_api_accepts_nulls_end_to_end(monkeypatch) -> None:
    """POST /bookings with JSON nulls for inapplicable fields returns 201."""
    monkeypatch.setattr(bookings, "get_repository", lambda: FakeBookingRepository())

    response = client.post(
        "/bookings",
        json={
            "customer_name": "Ana",
            "customer_phone": "+10000000001",
            "booking_type": "FOOD_ORDER",
            "service_type": "individual_food_order",
            "event_date": None,
            "event_time": None,
            "event_location": None,
            "guest_count": None,
            "package_id": None,
            "special_requests": None,
            "booking_items": [
                {"item_name": "Tray", "quantity": 1, "unit_price": "10.00"}
            ],
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "success"
