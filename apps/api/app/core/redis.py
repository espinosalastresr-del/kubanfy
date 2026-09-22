"""Redis client for locks, single-flight, rate limits, queues, temporary state.

Redis is NEVER the source of truth.
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as redis

from app.core.config import Settings, get_settings

_redis_client: redis.Redis | None = None


async def init_redis(settings: Settings | None = None) -> redis.Redis:
    global _redis_client
    settings = settings or get_settings()
    _redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=settings.redis_max_connections,
    )
    # Verify connection
    await _redis_client.ping()
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def get_redis() -> redis.Redis:
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client


async def get_redis_dependency() -> Any:
    """FastAPI dependency."""
    return get_redis()
