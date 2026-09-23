"""Background worker runner.

Polls PostgreSQL for jobs (source of truth), processes them, and
updates status. Redis is used only for coordination when needed.

Usage:
    python -m app.workers.runner
"""

from __future__ import annotations

import asyncio
import signal
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import get_settings
from app.core.database import async_session_factory, close_db, init_db
from app.core.logging import get_logger, setup_logging
from app.core.redis import close_redis, init_redis
from app.models.job import Job, JobType
from app.services.job import JobService

# Register built-in handlers
import app.workers.handlers  # noqa: F401, E402

logger = get_logger(__name__)

# Handler registry: job type -> async callable(job, session) -> dict | None
JobHandler = Callable[[Job, Any], Awaitable[dict[str, Any] | None]]
_handlers: dict[JobType, JobHandler] = {}


def register_handler(job_type: JobType):
    """Decorator to register a job handler."""

    def decorator(fn: JobHandler) -> JobHandler:
        _handlers[job_type] = fn
        return fn

    return decorator


async def _default_handler(job: Job, session: Any) -> dict[str, Any] | None:
    logger.warning("no_handler_for_job", job_type=job.type.value, job_id=str(job.id))
    return {"skipped": True, "reason": "no_handler"}


async def process_one(worker_id: str) -> bool:
    """Claim and process one job. Returns True if a job was processed."""
    if async_session_factory is None:
        raise RuntimeError("DB not initialized")

    async with async_session_factory() as session:
        service = JobService(session)
        job = await service.claim_next(worker_id=worker_id)
        if job is None:
            await session.commit()
            return False

        handler = _handlers.get(job.type, _default_handler)
        try:
            result = await handler(job, session)
            await service.complete(job.id, result=result)
            await session.commit()
        except Exception as exc:
            logger.exception("job_handler_error", job_id=str(job.id))
            await session.rollback()
            # New session for fail update
            async with async_session_factory() as session2:
                svc2 = JobService(session2)
                await svc2.fail(job.id, str(exc))
                await session2.commit()
        return True


async def run_worker(
    *,
    poll_interval: float = 1.0,
    idle_interval: float = 2.0,
) -> None:
    settings = get_settings()
    setup_logging(settings)
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    logger.info(
        "worker_starting",
        worker_id=worker_id,
        environment=settings.environment.value,
        registered_handlers=[t.value for t in _handlers],
    )

    init_db(settings)
    try:
        await init_redis(settings)
    except Exception as exc:
        logger.warning("worker_redis_unavailable", error=str(exc))

    stop = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("worker_shutdown_signal")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    try:
        while not stop.is_set():
            try:
                processed = await process_one(worker_id)
                if processed:
                    await asyncio.sleep(poll_interval)
                else:
                    await asyncio.sleep(idle_interval)
            except Exception:
                logger.exception("worker_loop_error")
                await asyncio.sleep(idle_interval)
    finally:
        await close_redis()
        await close_db()
        logger.info("worker_stopped", worker_id=worker_id)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
