"""Tests for the database health endpoint (Phase 1).

Unit tests use monkeypatching so they run without real Supabase credentials.
See test_db_integration.py for the real-credential check (skipped by default).
"""

from fastapi.testclient import TestClient

from app.api.routes import db_health
from app.integrations import supabase_client
from app.main import app

client = TestClient(app)


def test_db_health_not_configured(monkeypatch) -> None:
    """Without credentials /health/db returns 503, never the key."""
    monkeypatch.setattr(supabase_client, "is_configured", lambda: False)

    response = client.get("/health/db")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["database"] == "not_configured"
    assert "SUPABASE_SERVICE_ROLE_KEY" not in response.text


def test_db_health_connected(monkeypatch) -> None:
    """A reachable database returns 200 with database=connected."""
    monkeypatch.setattr(supabase_client, "is_configured", lambda: True)
    monkeypatch.setattr(db_health.supabase_client, "check_supabase_connection", lambda: None)

    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_db_health_unavailable(monkeypatch) -> None:
    """An unreachable database returns 503 without credential leakage."""
    monkeypatch.setattr(supabase_client, "is_configured", lambda: True)

    def fail() -> None:
        raise RuntimeError("Supabase query failed")

    monkeypatch.setattr(db_health.supabase_client, "check_supabase_connection", fail)

    response = client.get("/health/db")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["database"] == "unavailable"


def test_plain_health_still_works() -> None:
    """GET /health is unchanged by Phase 1."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
