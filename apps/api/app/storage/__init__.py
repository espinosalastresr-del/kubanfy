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
    StorageProvider,
    StoredObject,
)
from app.storage.local import LocalStorage
from app.storage.r2 import R2Storage

logger = get_logger(__name__)

__all__ = [
    "LocalStorage",
    "R2Storage",
    "SignedUrl",
    "StorageBucket",
    "StorageProvider",
    "StoredObject",
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
    if settings.environment == Environment.STAGING and settings.staging_use_local_storage:
        logger.info("storage_backend", backend="local-staging")
        return LocalStorage(
            public_base_url=settings.public_base_url,
            signing_secret=settings.jwt_secret_key,
        )
    # Production without R2 must never silently downgrade to local disk.
    logger.error("storage_r2_not_configured_in_non_dev")
    raise RuntimeError("R2 storage is required outside development/test")
