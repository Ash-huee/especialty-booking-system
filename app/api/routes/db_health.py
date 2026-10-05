"""Database health-check route (Phase 1).

`GET /health` in `health.py` is left untouched.
This router adds `GET /health/db` which verifies Supabase connectivity
without exposing any credentials.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.integrations import supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health/db")
def get_db_health() -> JSONResponse:
    """Check Supabase connectivity.

    Returns 200 when the database answers, otherwise 503 with a
    generic message (never credentials or raw driver errors).
    """
    if not supabase_client.is_configured():
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "not_configured",
                "detail": "Supabase credentials are not configured",
            },
        )
    try:
        supabase_client.check_supabase_connection()
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "database": "connected"},
        )
    except Exception:
        logger.exception("Database health check failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "unavailable",
                "detail": "Could not reach the database",
            },
        )
