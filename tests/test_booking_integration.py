"""Live booking-engine integration test (Phase 2).

SEPARATE from unit tests: skipped unless real Supabase credentials exist.
Performs a real FOOD_ORDER write (customer + booking + items), asserts the
deterministic outcome, then cleans up in dependency order
(items -> booking -> customer) to respect ON DELETE RESTRICT.

Run explicitly after the Phase 1 migration:
    pytest tests/test_booking_integration.py -v
"""

import os
import time

import pytest

CREDENTIALS_PRESENT = bool(
    os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

pytestmark = pytest.mark.skipif(
    not CREDENTIALS_PRESENT,
    reason="Supabase credentials not configured — skipping live booking test",
)


def test_live_food_order_booking() -> None:
    """End-to-end FOOD_ORDER through the real repository (never faked)."""
    from app.integrations import supabase_client
    from app.integrations.booking_repository import SupabaseBookingRepository
    from app.models.booking import BookingCreateRequest
    from app.services import booking_service
    from app.services.booking_service import BookingSuccess

    client = supabase_client.get_supabase_client()
    assert client is not None
    repository = SupabaseBookingRepository(client)

    unique_phone = f"+1555{int(time.time()) % 10000000:07d}"
    request = BookingCreateRequest(
        customer_name="Live Test",
        customer_phone=unique_phone,
        booking_type="FOOD_ORDER",
        service_type="individual_food_order",
        booking_items=[
            {"item_name": "Live tray", "quantity": 2, "unit_price": "10.00"},
        ],
    )

    result = booking_service.create_booking(request, repository)

    assert isinstance(result, BookingSuccess)
    assert result.booking_status == "PENDING"
    assert result.estimated_price == "20.00"

    # Cleanup in FK-safe order; failures must not mask the assertion above.
    try:
        booking_id = result.booking_id
        items = (
            client.table("booking_items")
            .select("id")
            .eq("booking_id", booking_id)
            .execute()
            .data
            or []
        )
        for item in items:
            client.table("booking_items").delete().eq("id", item["id"]).execute()
        booking = (
            client.table("bookings").select("customer_id").eq("id", booking_id).execute().data
        )
        client.table("bookings").delete().eq("id", booking_id).execute()
        if booking:
            client.table("customers").delete().eq("id", booking[0]["customer_id"]).execute()
    except Exception as exc:  # pragma: no cover - cleanup best effort
        pytest.fail(f"Live booking passed but cleanup failed: {exc}")
