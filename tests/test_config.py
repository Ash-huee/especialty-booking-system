"""Tests for environment-variable configuration (Phase 1).

These tests use monkeypatch so they never need real secrets.
"""

from app.core.config import Settings


def test_defaults_without_env(monkeypatch) -> None:
    """Defaults apply when no environment variables are set."""
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    settings = Settings()

    assert settings.APP_NAME == "Especialty"
    assert settings.APP_ENV == "development"
    assert settings.DEBUG is True
    assert settings.SUPABASE_URL == ""
    assert settings.SUPABASE_SERVICE_ROLE_KEY == ""
    assert settings.is_supabase_configured() is False


def test_loads_values_from_env(monkeypatch) -> None:
    """Settings pick up values from environment variables."""
    monkeypatch.setenv("APP_NAME", "TestApp")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "False")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "dummy-key-for-test")

    settings = Settings()

    assert settings.APP_NAME == "TestApp"
    assert settings.APP_ENV == "test"
    assert settings.DEBUG is False
    assert settings.SUPABASE_URL == "https://example.supabase.co"
    assert settings.SUPABASE_SERVICE_ROLE_KEY == "dummy-key-for-test"
    assert settings.is_supabase_configured() is True


def test_supabase_needs_both_values(monkeypatch) -> None:
    """Both URL and key are required — one alone is not enough."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    assert Settings().is_supabase_configured() is False
