"""API tests for POST /bookings (Phase 2).

The route stays thin: HTTP mapping is tested here with a fake
repository, so no live database is needed.
"""

from fastapi.testclient import TestClient

from app.api.routes import bookings
from app.main import app
from tests.fakes import FakeBookingRepository, make_food_order_request, make_request

client = TestClient(app)


def _event_payload() -> dict:
    return {
        "customer_name": "Ana Lopez",
        "customer_phone": "+10000000001",
        "booking_type": "EVENT",
        "service_type": "catering",
        "event_date": "2030-06-15",
        "event_time": "18:00:00",
        "event_location": "123 Main Hall",
        "guest_count": 20,
    }


def test_post_bookings_success_returns_201(monkeypatch) -> None:
    """Valid EVENT → 201 with booking_id, PENDING status, price."""
    monkeypatch.setattr(bookings, "get_repository", lambda: FakeBookingRepository())

    response = client.post("/bookings", json=_event_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["booking_id"]
    assert body["booking_status"] == "PENDING"
    assert "booking_items" not in body  # No DB internals leaked.


def test_post_bookings_validation_error_returns_422(monkeypatch) -> None:
    """Missing guest_count → 422 with structured {field, code, message}."""
    monkeypatch.setattr(bookings, "get_repository", lambda: FakeBookingRepository())

    payload = _event_payload()
    del payload["guest_count"]
    response = client.post("/bookings", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "validation_error"
    assert body["errors"][0]["field"] == "guest_count"
    assert body["errors"][0]["code"] == "REQUIRED_GUEST_COUNT"
    assert body["errors"][0]["message"]


def test_post_bookings_capacity_returns_409(monkeypatch) -> None:
    """Full date → 409 with EVENT_CAPACITY_REACHED (same body shape)."""
    monkeypatch.setattr(
        bookings,
        "get_repository",
        lambda: FakeBookingRepository(max_events=2, active_count=2),
    )

    response = client.post("/bookings", json=_event_payload())

    assert response.status_code == 409
    body = response.json()
    assert body["status"] == "validation_error"
    assert body["errors"][0]["code"] == "EVENT_CAPACITY_REACHED"


def test_post_bookings_handoff_returns_202(monkeypatch) -> None:
    """DB failure → 202 human_handoff, no internals exposed."""
    monkeypatch.setattr(
        bookings,
        "get_repository",
        lambda: FakeBookingRepository(fail_on=("get_max_events_per_day",)),
    )

    response = client.post("/bookings", json=_event_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "human_handoff"
    assert body["booking_status"] == "HUMAN_HANDOFF"


def test_post_bookings_unconfigured_returns_503(monkeypatch) -> None:
    """No Supabase credentials → 503 without leaking anything."""
    monkeypatch.setattr(bookings, "get_repository", lambda: None)

    response = client.post("/bookings", json=_event_payload())

    assert response.status_code == 503
    assert response.json()["status"] == "error"


def test_post_food_order_success(monkeypatch) -> None:
    """Valid FOOD_ORDER → 201 with summed Decimal price."""
    monkeypatch.setattr(bookings, "get_repository", lambda: FakeBookingRepository())

    response = client.post(
        "/bookings",
        json={
            "customer_name": "Ana",
            "customer_phone": "+10000000001",
            "booking_type": "FOOD_ORDER",
            "service_type": "individual_food_order",
            "booking_items": [
                {"item_name": "Tray", "quantity": 2, "unit_price": "10.00"}
            ],
        },
    )

    assert response.status_code == 201
    assert response.json()["estimated_price"] == "20.00"


def test_models_importable_for_docs() -> None:
    """Sanity: request helpers used above stay importable."""
    assert make_request().booking_type == "EVENT"
    assert make_food_order_request().booking_type == "FOOD_ORDER"
