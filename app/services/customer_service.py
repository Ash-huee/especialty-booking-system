"""Shared customer resolution (Phase 3).

Single home for the deterministic rule used by both the booking engine
(Phase 2) and the conversation layer (Phase 3):

1. exact phone match wins,
2. otherwise exact email match (when an email was supplied),
3. otherwise create a new customer.

No fuzzy matching, no AI. Database problems raise RepositoryError so
callers can map them to handoff/error responses without leaking internals.
"""

from app.integrations.booking_repository import RepositoryError
from app.models.customer import CustomerData


def find_or_create_customer(customer: CustomerData, repository) -> tuple[dict, bool]:
    """Return (customer row, created_new) for the matching customer.

    `repository` is any object with `find_customer_by_phone`,
    `find_customer_by_email`, and `create_customer` (real repositories
    and test fakes alike).
    """
    try:
        existing = repository.find_customer_by_phone(customer.phone)
        if existing is None and customer.email:
            existing = repository.find_customer_by_email(customer.email)
        if existing is None:
            existing = repository.create_customer(
                customer.name, customer.phone, customer.email
            )
            created_new = True
        else:
            created_new = False
        customer_id = existing.get("id")
        if not customer_id:
            raise RepositoryError("Customer record has no id")
        return existing, created_new
    except RepositoryError:
        raise
    except Exception as exc:
        raise RepositoryError("Customer resolution failed") from exc
