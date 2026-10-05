"""Supabase data-access layer for the booking engine (Phase 2).

The booking service talks to THIS class — never to raw Supabase calls.
That keeps SQL/PostgREST details in one place and makes the service
testable with a fake repository (see tests/).

Unexpected database problems raise RepositoryError with a generic
message. The service maps those to HUMAN_HANDOFF without leaking
internals to the API caller.
"""


class RepositoryError(Exception):
    """Generic data-access failure (cause is chained, never exposed via API)."""


class SupabaseBookingRepository:
    """Thin wrapper around a Supabase client for booking operations."""

    def __init__(self, client) -> None:
        self.client = client

    # -- customers --------------------------------------------------------

    def find_customer_by_phone(self, phone: str) -> dict | None:
        """Return the first customer with this exact phone, or None."""
        try:
            response = (
                self.client.table("customers")
                .select("*")
                .eq("phone", phone)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Customer lookup failed") from exc
        rows = response.data or []
        return rows[0] if rows else None

    def find_customer_by_email(self, email: str) -> dict | None:
        """Return the first customer with this exact email, or None."""
        try:
            response = (
                self.client.table("customers")
                .select("*")
                .eq("email", email)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Customer lookup failed") from exc
        rows = response.data or []
        return rows[0] if rows else None

    def create_customer(self, name: str, phone: str, email: str | None) -> dict:
        """Insert a customer row and return it (must include its id)."""
        try:
            response = (
                self.client.table("customers")
                .insert({"name": name, "phone": phone, "email": email})
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Customer creation failed") from exc
        rows = response.data or []
        if not rows or "id" not in rows[0]:
            raise RepositoryError("Customer creation failed")
        return rows[0]

    # -- packages / settings ----------------------------------------------

    def get_package(self, package_id: str) -> dict | None:
        """Return a package row by id, or None when it does not exist."""
        try:
            response = (
                self.client.table("packages")
                .select("*")
                .eq("id", package_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Package lookup failed") from exc
        rows = response.data or []
        return rows[0] if rows else None

    def get_max_events_per_day(self) -> int:
        """Read business_settings.max_events_per_day (never hard-coded).

        Raises RepositoryError when the setting is missing or invalid —
        the service treats that as HUMAN_HANDOFF, not a guessed default.
        """
        try:
            response = (
                self.client.table("business_settings")
                .select("max_events_per_day")
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Settings lookup failed") from exc
        rows = response.data or []
        if not rows:
            raise RepositoryError("Business settings are missing")
        try:
            value = int(rows[0]["max_events_per_day"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RepositoryError("Business settings are invalid") from exc
        if value <= 0:
            raise RepositoryError("Business settings are invalid")
        return value

    def count_active_events(self, event_date) -> int:
        """Count EVENT bookings on a date, excluding CANCELLED ones.

        Food orders never consume event capacity (filtered by type).
        """
        try:
            response = (
                self.client.table("bookings")
                .select("id,status")
                .eq("booking_type", "EVENT")
                .eq("event_date", event_date.isoformat())
                .neq("status", "CANCELLED")
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Capacity check failed") from exc
        return len(response.data or [])

    # -- bookings ----------------------------------------------------------

    def create_booking(self, payload: dict) -> dict:
        """Insert a booking row and return it (must include its id)."""
        try:
            response = self.client.table("bookings").insert(payload).execute()
        except Exception as exc:
            raise RepositoryError("Booking creation failed") from exc
        rows = response.data or []
        if not rows or "id" not in rows[0]:
            raise RepositoryError("Booking creation failed")
        return rows[0]

    def create_booking_items(self, booking_id: str, items: list[dict]) -> list[dict]:
        """Insert booking-item rows linked to a booking."""
        rows_to_insert = [{**item, "booking_id": booking_id} for item in items]
        try:
            response = (
                self.client.table("booking_items").insert(rows_to_insert).execute()
            )
        except Exception as exc:
            raise RepositoryError("Booking items creation failed") from exc
        return response.data or []
