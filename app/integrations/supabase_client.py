"""Supabase client for Phase 1.

Kept separate from business logic and API routes so the connection
setup is easy to find and easy to test.

Security: the service-role key is server-side only. This module never
prints, logs, or returns the key.
"""

from app.core.config import settings

try:
    from supabase import Client, create_client
except ImportError:  # Allows unit tests to run without the dependency installed.
    Client = None  # type: ignore
    create_client = None  # type: ignore


def is_configured() -> bool:
    """Return True when Supabase credentials are present."""
    return settings.is_supabase_configured()


def get_supabase_client() -> "Client | None":
    """Create a Supabase client, or return None when not configured.

    Returns None (instead of raising) so the `/health/db` endpoint can
    report "not configured" and normal unit tests can run without
    real credentials.
    """
    if not is_configured():
        return None
    if create_client is None:
        raise RuntimeError("supabase package is not installed")
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )


def check_supabase_connection() -> None:
    """Verify the backend can reach Supabase.

    Raises:
        RuntimeError: if credentials are missing or the query fails.
            The error message is generic and never includes the key.
    """
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase is not configured")
    try:
        # Lightweight read against the settings table created by the
        # Phase 1 migration. limit(1) keeps it cheap.
        client.table("business_settings").select("id").limit(1).execute()
    except Exception as exc:
        raise RuntimeError("Supabase query failed") from exc
