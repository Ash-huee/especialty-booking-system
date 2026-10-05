"""Tests for Supabase client initialization (Phase 1).

Unit tests only — no real credentials or network calls.
"""

import pytest

from app.integrations import supabase_client


def test_not_configured_returns_none(monkeypatch) -> None:
    """Without credentials the client returns None (no fake connection)."""
    monkeypatch.setattr(supabase_client.settings, "SUPABASE_URL", "")
    monkeypatch.setattr(supabase_client.settings, "SUPABASE_SERVICE_ROLE_KEY", "")

    assert supabase_client.is_configured() is False
    assert supabase_client.get_supabase_client() is None


def test_check_raises_when_not_configured(monkeypatch) -> None:
    """check_supabase_connection raises a generic error when unconfigured."""
    monkeypatch.setattr(supabase_client.settings, "SUPABASE_URL", "")
    monkeypatch.setattr(supabase_client.settings, "SUPABASE_SERVICE_ROLE_KEY", "")

    with pytest.raises(RuntimeError, match="not configured"):
        supabase_client.check_supabase_connection()


def test_get_client_uses_configured_values(monkeypatch) -> None:
    """When configured, the client is built from settings (mocked)."""
    monkeypatch.setattr(supabase_client.settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(supabase_client.settings, "SUPABASE_SERVICE_ROLE_KEY", "dummy-key")

    captured = {}

    def fake_create_client(url: str, key: str) -> str:
        captured["url"] = url
        captured["key"] = key
        return "fake-client"

    monkeypatch.setattr(supabase_client, "create_client", fake_create_client)

    assert supabase_client.get_supabase_client() == "fake-client"
    assert captured["url"] == "https://example.supabase.co"
    assert captured["key"] == "dummy-key"


def test_check_connection_success(monkeypatch) -> None:
    """check_supabase_connection passes when the query succeeds (mocked)."""

    class FakeQuery:
        def select(self, *args, **kwargs) -> "FakeQuery":
            return self

        def limit(self, *args, **kwargs) -> "FakeQuery":
            return self

        def execute(self) -> dict:
            return {"data": []}

    class FakeClient:
        def table(self, name: str) -> FakeQuery:
            assert name == "business_settings"
            return FakeQuery()

    monkeypatch.setattr(supabase_client.settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(supabase_client.settings, "SUPABASE_SERVICE_ROLE_KEY", "dummy-key")
    monkeypatch.setattr(supabase_client, "get_supabase_client", lambda: FakeClient())

    # Should not raise.
    supabase_client.check_supabase_connection()


def test_check_connection_failure_hides_details(monkeypatch) -> None:
    """A failing query raises RuntimeError without leaking the key."""

    class BrokenClient:
        def table(self, name: str) -> "BrokenClient":
            raise ConnectionError("db is down")

    monkeypatch.setattr(supabase_client.settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(supabase_client.settings, "SUPABASE_SERVICE_ROLE_KEY", "super-secret-key")
    monkeypatch.setattr(supabase_client, "get_supabase_client", lambda: BrokenClient())

    with pytest.raises(RuntimeError, match="query failed") as exc_info:
        supabase_client.check_supabase_connection()

    assert "super-secret-key" not in str(exc_info.value)
