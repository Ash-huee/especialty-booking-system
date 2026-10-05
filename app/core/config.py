"""Application configuration using environment variables.

This module is intentionally simple so it is easy to understand
for a junior backend developer:

* Values come from environment variables.
* Sensible development defaults are provided.
* No secrets are stored in source code.
* A real `.env` file is never committed (see `.env.example`).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load the project's root `.env` file (especialty/.env) before any
# os.getenv() calls below. override=False (the default) keeps actual
# environment variables taking precedence over .env values.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _get_bool(name: str, default: bool) -> bool:
    """Read a boolean environment variable.

    Accepts: "true", "1", "yes" (case-insensitive) as True.
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("true", "1", "yes")


class Settings:
    """Simple container for application settings."""

    def __init__(self) -> None:
        self.APP_NAME: str = os.getenv("APP_NAME", "Especialty")
        self.APP_ENV: str = os.getenv("APP_ENV", "development")
        self.DEBUG: bool = _get_bool("DEBUG", True)
        # Supabase connection (Phase 1). Server-side only — never log
        # or expose SUPABASE_SERVICE_ROLE_KEY. Empty string means
        # "not configured" so local unit tests run without credentials.
        self.SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
        self.SUPABASE_SERVICE_ROLE_KEY: str = os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY", ""
        )

    def is_supabase_configured(self) -> bool:
        """Return True only when both Supabase variables are set."""
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_ROLE_KEY)


settings = Settings()
