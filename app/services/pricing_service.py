"""Deterministic price calculations (Phase 2).

All money uses Decimal — never float — so 0.1 + 0.2 style errors
cannot corrupt totals. Results are quantized to 2 decimal places
to match the NUMERIC(12, 2) columns in the database.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_CENTS = Decimal("0.01")


def to_decimal(value: object) -> Decimal:
    """Convert a value to Decimal safely (strings preferred over floats)."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid monetary value: {value!r}") from exc


def money(value: Decimal) -> Decimal:
    """Round a Decimal to 2 decimal places (cents)."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def calculate_event_price(guest_count: int, price_per_person: Decimal) -> Decimal:
    """EVENT price = guest_count x package.price_per_person."""
    return money(to_decimal(guest_count) * to_decimal(price_per_person))


def calculate_food_order_total(items: list) -> Decimal:
    """FOOD_ORDER total = sum(quantity x unit_price) over all items."""
    total = Decimal("0")
    for item in items:
        quantity = to_decimal(item.quantity if hasattr(item, "quantity") else item["quantity"])
        unit_price = to_decimal(
            item.unit_price if hasattr(item, "unit_price") else item["unit_price"]
        )
        total += quantity * unit_price
    return money(total)
