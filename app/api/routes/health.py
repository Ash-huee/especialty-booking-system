"""Health-check route.

Kept in its own router so `main.py` stays small and
new feature routers can be added in the same pattern later.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> dict[str, str]:
    """Return a simple health status used by monitoring and tests."""
    return {"status": "ok"}
