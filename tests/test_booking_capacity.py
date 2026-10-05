"""Unit tests for the 2-events-per-day capacity rule (Phase 2).

The limit always comes from the repository (business_settings), never
hard-coded. CANCELLED bookings never count — enforced in the repository
query (verified at the query level below).
"""

from tests.fakes import FakeBookingRepository, make_request

from app.services import booking_service
from app.services.booking_service import (
    BookingSuccess,
    BookingValidationFailure,
)


def test_zero_existing_events_allowed() -> None:
    """0 existing events with limit 2 → booking created."""
    repo = FakeBookingRepository(max_events=2, active_count=0)
    result = booking_service.create_booking(make_request(), repo)
    assert isinstance(result, BookingSuccess)
    assert len(repo.created_bookings) == 1


def test_one_existing_event_allowed() -> None:
    """1 existing event with limit 2 → booking created."""
    repo = FakeBookingRepository(max_events=2, active_count=1)
    result = booking_service.create_booking(make_request(), repo)
    assert isinstance(result, BookingSuccess)


def test_two_existing_events_rejected() -> None:
    """2 existing events with limit 2 → EVENT_CAPACITY_REACHED, nothing stored."""
    repo = FakeBookingRepository(max_events=2, active_count=2)
    result = booking_service.create_booking(make_request(), repo)
    assert isinstance(result, BookingValidationFailure)
    assert result.errors[0].code == "EVENT_CAPACITY_REACHED"
    assert result.errors[0].field == "event_date"
    assert repo.created_bookings == []  # Must not create when full.


def test_limit_comes_from_settings_not_hardcoded() -> None:
    """A limit of 1 rejects the second event (proves no hard-coded 2)."""
    repo = FakeBookingRepository(max_events=1, active_count=1)
    result = booking_service.create_booking(make_request(), repo)
    assert isinstance(result, BookingValidationFailure)
    assert result.errors[0].code == "EVENT_CAPACITY_REACHED"


def test_food_orders_ignore_capacity() -> None:
    """FOOD_ORDER never checks event capacity, even on a full date."""
    from tests.fakes import make_food_order_request

    repo = FakeBookingRepository(max_events=2, active_count=99)
    result = booking_service.create_booking(make_food_order_request(), repo)
    assert isinstance(result, BookingSuccess)


def test_repository_query_excludes_cancelled() -> None:
    """The Supabase query filters type=EVENT and status != CANCELLED."""
    from app.integrations.booking_repository import SupabaseBookingRepository

    calls: dict = {}

    class FakeQuery:
        def select(self, *args):
            calls["select"] = args
            return self

        def eq(self, column, value):
            calls.setdefault("eq", []).append((column, value))
            return self

        def neq(self, column, value):
            calls.setdefault("neq", []).append((column, value))
            return self

        def execute(self):
            class Response:
                data = [{"id": "a"}, {"id": "b"}]

            return Response()

    class FakeClient:
        def table(self, name):
            calls["table"] = name
            return FakeQuery()

    from datetime import date

    repo = SupabaseBookingRepository(FakeClient())
    assert repo.count_active_events(date(2030, 6, 15)) == 2
    assert calls["table"] == "bookings"
    assert ("booking_type", "EVENT") in calls["eq"]
    assert ("event_date", "2030-06-15") in calls["eq"]
    assert ("status", "CANCELLED") in calls["neq"]
