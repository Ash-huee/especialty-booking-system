"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI

from app.api.routes import db_health, health
from app.core.config import settings

# Basic logging setup: enough to see startup and request info in development.
# DEBUG=True -> detailed logs, DEBUG=False -> standard info logs.
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)

# Register routers here. Each feature gets its own router module
# instead of defining all endpoints directly in this file.
app.include_router(health.router)
app.include_router(db_health.router)

logger.info(
    "Starting %s (env=%s, debug=%s)",
    settings.APP_NAME,
    settings.APP_ENV,
    settings.DEBUG,
)
