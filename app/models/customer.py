"""Customer data structures and basic normalization (Phase 2).

Business decisions (matching, creation) live in the booking service.
This module only normalizes raw input and checks the simplest rules.
"""

from app.models.booking import ValidationError


class CustomerData:
    """Trimmed customer fields extracted from a booking request."""

    def __init__(self, name: str, phone: str, email: str | None) -> None:
        self.name = name
        self.phone = phone
        self.email = email


def normalize_customer_data(name: str, phone: str, email: str) -> CustomerData:
    """Trim whitespace. Blank email becomes None (email is optional)."""
    clean_email = (email or "").strip()
    return CustomerData(
        name=(name or "").strip(),
        phone=(phone or "").strip(),
        email=clean_email if clean_email else None,
    )


def is_valid_email(email: str) -> bool:
    """Basic email format check (one @, a dot after it, no spaces).

    Intentionally simple for Phase 2. Production would use a dedicated
    validator, but this catches obvious typos without a new dependency.
    """
    if " " in email:
        return False
    if email.count("@") != 1:
        return False
    local, _, domain = email.partition("@")
    if not local or not domain:
        return False
    if "." not in domain:
        return False
    return True


def validate_customer(customer: CustomerData) -> list[ValidationError]:
    """Check customer rules shared by EVENT and FOOD_ORDER."""
    errors: list[ValidationError] = []
    if not customer.name:
        errors.append(
            ValidationError(
                field="customer_name",
                code="REQUIRED_CUSTOMER_NAME",
                message="Customer name is required.",
            )
        )
    if not customer.phone:
        errors.append(
            ValidationError(
                field="customer_phone",
                code="REQUIRED_CUSTOMER_PHONE",
                message="Customer phone is required.",
            )
        )
    if customer.email is not None and not is_valid_email(customer.email):
        errors.append(
            ValidationError(
                field="customer_email",
                code="INVALID_EMAIL",
                message="Email format is invalid.",
            )
        )
    return errors
