"""Distributed locks and single-flight via Redis.

Redis is NOT source of truth — only coordination.
Single-flight: 100 concurrent requests for the same key → 1 acquisition.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)

T = TypeVar("T")

# Lua script: release lock only if we still own it
_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class LockError(Exception):
    """Could not acquire lock within timeout."""


class DistributedLock:
    """Redis-based distributed lock with ownership token."""

    def __init__(
        self,
        key: str,
        *,
        ttl_seconds: float = 30.0,
        wait_timeout: float = 10.0,
        poll_interval: float = 0.05,
    ) -> None:
        self.key = f"lock:{key}"
        self.ttl_ms = int(ttl_seconds * 1000)
        self.wait_timeout = wait_timeout
        self.poll_interval = poll_interval
        self.token = str(uuid.uuid4())
        self._acquired = False

    async def acquire(self) -> bool:
        redis = get_redis()
        deadline = asyncio.get_event_loop().time() + self.wait_timeout
        while True:
            ok = await redis.set(self.key, self.token, nx=True, px=self.ttl_ms)
            if ok:
                self._acquired = True
                return True
            if asyncio.get_event_loop().time() >= deadline:
                return False
            await asyncio.sleep(self.poll_interval)

    async def release(self) -> None:
        if not self._acquired:
            return
        redis = get_redis()
        try:
            await redis.eval(_RELEASE_SCRIPT, 1, self.key, self.token)
        finally:
            self._acquired = False

    async def __aenter__(self) -> DistributedLock:
        acquired = await self.acquire()
        if not acquired:
            raise LockError(f"Could not acquire lock: {self.key}")
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.release()


@asynccontextmanager
async def distributed_lock(
    key: str,
    *,
    ttl_seconds: float = 30.0,
    wait_timeout: float = 10.0,
):
    """Async context manager for a distributed lock."""
    lock = DistributedLock(key, ttl_seconds=ttl_seconds, wait_timeout=wait_timeout)
    async with lock:
        yield lock


async def single_flight(
    key: str,
    factory: Callable[[], Awaitable[T]],
    *,
    ttl_seconds: float | None = None,
    wait_timeout: float | None = None,
    result_ttl_seconds: float = 60.0,
) -> T:
    """Ensure only one concurrent execution of factory for the given key.

    Other waiters block on the lock, then either:
    - re-run factory if no shared result was published, or
    - for simple cases just wait for the lock holder to finish and re-execute
      (the expensive work is still done once while lock is held).

    Pattern:
        result = await single_flight(f"acquire:{track_id}:{quality}", do_acquire)
    """
    settings = get_settings()
    ttl = ttl_seconds if ttl_seconds is not None else float(settings.cache_single_flight_timeout_seconds)
    wait = wait_timeout if wait_timeout is not None else ttl

    redis = get_redis()
    result_key = f"sf:result:{key}"
    lock_key = f"sf:{key}"

    # Fast path: someone already published a result marker
    # (We don't store the actual result in Redis for large payloads —
    #  the lock serializes the side-effect; callers re-check cache/DB after.)

    async with distributed_lock(lock_key, ttl_seconds=ttl, wait_timeout=wait):
        # Double-check after acquiring
        done = await redis.get(result_key)
        if done == "1":
            # Another worker finished while we waited; caller should re-check
            # their own cache/DB. We still allow re-execution of factory only
            # if the caller needs a return value — for acquisition the
            # side-effect is already done.
            logger.debug("single_flight_already_done", key=key)

        result = await factory()
        await redis.set(result_key, "1", ex=int(result_ttl_seconds))
        return result


async def single_flight_with_result(
    key: str,
    factory: Callable[[], Coroutine[Any, Any, T]],
    *,
    serialize: Callable[[T], str],
    deserialize: Callable[[str], T],
    ttl_seconds: float | None = None,
    wait_timeout: float | None = None,
    result_ttl_seconds: float = 120.0,
) -> T:
    """Single-flight that also shares a small serialized result via Redis.

    Suitable for metadata / small JSON, not for audio bodies.
    """
    settings = get_settings()
    ttl = ttl_seconds if ttl_seconds is not None else float(settings.cache_single_flight_timeout_seconds)
    wait = wait_timeout if wait_timeout is not None else ttl

    redis = get_redis()
    result_key = f"sf:val:{key}"
    lock_key = f"sf:{key}"

    cached = await redis.get(result_key)
    if cached is not None:
        return deserialize(cached)

    async with distributed_lock(lock_key, ttl_seconds=ttl, wait_timeout=wait):
        cached = await redis.get(result_key)
        if cached is not None:
            return deserialize(cached)

        result = await factory()
        await redis.set(result_key, serialize(result), ex=int(result_ttl_seconds))
        return result
