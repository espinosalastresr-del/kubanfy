"""Run a bounded batch of durable background jobs and exit.

Cloudflare Cron triggers invoke this command in a dedicated Container. Processing
one job per invocation keeps FFmpeg work isolated from API requests and avoids
a permanently running worker process.
"""

from __future__ import annotations

import asyncio
import uuid

from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.logging import get_logger, setup_logging
from app.core.redis import close_redis, init_redis
from app.workers.runner import process_one

logger = get_logger(__name__)


async def run_batch() -> bool:
    settings = get_settings()
    setup_logging(settings)
    worker_id = f"cron-worker-{uuid.uuid4().hex[:8]}"
    logger.info(
        "worker_batch_starting",
        worker_id=worker_id,
        environment=settings.environment.value,
        max_jobs=1,
    )

    init_db(settings)
    redis_ready = False
    try:
        try:
            await init_redis(settings)
            redis_ready = True
        except Exception as exc:
            # PostgreSQL is the source of truth for jobs. Redis is optional for
            # this runner and must not prevent audio transcoding from starting.
            logger.warning("worker_redis_unavailable", error=type(exc).__name__)

        processed = await process_one(worker_id)
        logger.info("worker_batch_finished", worker_id=worker_id, processed=processed)
        return processed
    finally:
        if redis_ready:
            await close_redis()
        await close_db()


def main() -> None:
    asyncio.run(run_batch())


if __name__ == "__main__":
    main()
