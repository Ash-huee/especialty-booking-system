"""Unit tests for Decimal-safe pricing (Phase 2)."""

from decimal import Decimal

from app.models.booking import BookingItemInput
from app.services import pricing_service


def test_event_price_multiplies_guests_by_package() -> None:
    """100 guests x 25.50 = 2550.00."""
    result = pricing_service.calculate_event_price(100, Decimal("25.50"))
    assert result == Decimal("2550.00")


def test_food_order_total_sums_lines() -> None:
    """2 x 10.00 + 3 x 5.50 = 36.50."""
    items = [
        BookingItemInput(item_name="A", quantity=2, unit_price=Decimal("10.00")),
        BookingItemInput(item_name="B", quantity=3, unit_price=Decimal("5.50")),
    ]
    assert pricing_service.calculate_food_order_total(items) == Decimal("36.50")


def test_decimal_safe_not_float() -> None:
    """3 x 0.10 = 0.30 exactly (float would give 0.30000000000000004)."""
    items = [BookingItemInput(item_name="A", quantity=3, unit_price=Decimal("0.10"))]
    assert pricing_service.calculate_food_order_total(items) == Decimal("0.30")


def test_money_rounds_to_cents() -> None:
    """Fractions of a cent round half-up to 2 decimals."""
    assert pricing_service.money(Decimal("2.345")) == Decimal("2.35")
    assert pricing_service.money(Decimal("2.344")) == Decimal("2.34")
