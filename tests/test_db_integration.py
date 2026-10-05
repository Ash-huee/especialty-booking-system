"""Real Supabase integration test (Phase 1).

This is SEPARATE from the normal unit-test suite:
* It is skipped automatically when SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
  are not set, so `pytest` passes without credentials.
* Run it explicitly after applying the SQL migration and configuring `.env`:
      pytest tests/test_db_integration.py -v
* It performs a real lightweight query and never fakes success.
"""

import os

import pytest

from app.integrations import supabase_client

CREDENTIALS_PRESENT = bool(
    os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

pytestmark = pytest.mark.skipif(
    not CREDENTIALS_PRESENT,
    reason="Supabase credentials not configured — skipping live DB test",
)


def test_live_supabase_connection() -> None:
    """Verify the backend can really reach Supabase (requires migration)."""
    assert supabase_client.is_configured() is True
    # Raises RuntimeError if the database is unreachable. No fake success.
    supabase_client.check_supabase_connection()
