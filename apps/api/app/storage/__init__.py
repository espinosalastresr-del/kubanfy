"""Object storage layer.

Prefer R2 when configured; fall back to LocalStorage in development/tests.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Environment, get_settings
from app.core.logging import get_logger
from app.storage.base import (
    SignedUrl,
    StorageBucket,
    StoredObject,
    StorageProvider,
)
from app.storage.local import LocalStorage
from app.storage.r2 import R2Storage

logger = get_logger(__name__)

__all__ = [
    "StorageProvider",
    "StorageBucket",
    "StoredObject",
    "SignedUrl",
    "LocalStorage",
    "R2Storage",
    "get_storage",
]


@lru_cache
def get_storage() -> StorageProvider:
    """Return the configured storage backend (cached)."""
    settings = get_settings()
    if settings.r2_configured:
        logger.info("storage_backend", backend="r2")
        return R2Storage(settings)
    if settings.environment in (Environment.DEVELOPMENT, Environment.TEST):
        logger.info("storage_backend", backend="local")
        return LocalStorage()
    # Production without R2 is a misconfiguration — still return local
    # but log loudly so ops notices.
    logger.error("storage_r2_not_configured_in_non_dev")
    return LocalStorage()
