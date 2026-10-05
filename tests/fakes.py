"""Shared fake repository for booking-engine unit tests.

Mimics SupabaseBookingRepository's method names with in-memory data,
so unit tests never need a live database.
"""

from app.integrations.booking_repository import RepositoryError

ACTIVE_PACKAGE_ID = "11111111-1111-1111-1111-111111111111"
INACTIVE_PACKAGE_ID = "22222222-2222-2222-2222-222222222222"


def make_request(**overrides):
    """Build a BookingCreateRequest dict with sane EVENT defaults."""
    from app.models.booking import BookingCreateRequest

    base = {
        "customer_name": "Ana Lopez",
        "customer_phone": "+10000000001",
        "customer_email": "",
        "booking_type": "EVENT",
        "service_type": "catering",
        "event_date": "2030-06-15",
        "event_time": "18:00:00",
        "event_location": "123 Main Hall",
        "guest_count": 50,
        "package_id": None,
        "booking_items": [],
    }
    base.update(overrides)
    return BookingCreateRequest(**base)


def make_food_order_request(**overrides):
    """Build a BookingCreateRequest dict with sane FOOD_ORDER defaults."""
    base = {
        "customer_name": "Ana Lopez",
        "customer_phone": "+10000000001",
        "customer_email": "",
        "booking_type": "FOOD_ORDER",
        "service_type": "individual_food_order",
        "booking_items": [
            {"item_name": "Chicken tray", "quantity": 2, "unit_price": "10.00"},
        ],
    }
    base.update(overrides)
    return make_request(**base)


class FakeBookingRepository:
    """In-memory stand-in for SupabaseBookingRepository."""

    def __init__(
        self,
        packages=None,
        max_events: int = 2,
        active_count: int = 0,
        existing_customers=None,
        fail_on=(),
    ) -> None:
        self.packages = packages if packages is not None else {}
        self.max_events = max_events
        self.active_count = active_count
        self.customers = list(existing_customers or [])
        self.fail_on = set(fail_on)
        self.created_bookings: list[dict] = []
        self.created_items: list[dict] = []
        self.created_customers: list[dict] = []
        self._next_id = 1000

    def _new_id(self) -> str:
        self._next_id += 1
        return f"fake-id-{self._next_id}"

    def _maybe_fail(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(f"Fake failure in {method}")

    # -- customers ------------------------------------------------------
    def find_customer_by_phone(self, phone: str) -> dict | None:
        self._maybe_fail("find_customer_by_phone")
        for customer in self.customers + self.created_customers:
            if customer.get("phone") == phone:
                return customer
        return None

    def find_customer_by_email(self, email: str) -> dict | None:
        self._maybe_fail("find_customer_by_email")
        for customer in self.customers + self.created_customers:
            if customer.get("email") == email:
                return customer
        return None

    def create_customer(self, name: str, phone: str, email: str | None) -> dict:
        self._maybe_fail("create_customer")
        row = {"id": self._new_id(), "name": name, "phone": phone, "email": email}
        self.created_customers.append(row)
        return row

    # -- packages / settings --------------------------------------------
    def get_package(self, package_id: str) -> dict | None:
        self._maybe_fail("get_package")
        return self.packages.get(package_id)

    def get_max_events_per_day(self) -> int:
        self._maybe_fail("get_max_events_per_day")
        return self.max_events

    def count_active_events(self, event_date) -> int:
        self._maybe_fail("count_active_events")
        return self.active_count

    # -- bookings --------------------------------------------------------
    def create_booking(self, payload: dict) -> dict:
        self._maybe_fail("create_booking")
        row = {"id": self._new_id(), **payload}
        self.created_bookings.append(row)
        return row

    def create_booking_items(self, booking_id: str, items: list[dict]) -> list[dict]:
        self._maybe_fail("create_booking_items")
        rows = [{**item, "booking_id": booking_id} for item in items]
        self.created_items.extend(rows)
        return rows


def active_package(price: str = "25.50") -> dict:
    """One active package row for tests."""
    return {
        "id": ACTIVE_PACKAGE_ID,
        "name": "Fiesta Package",
        "price_per_person": price,
        "is_active": True,
    }
