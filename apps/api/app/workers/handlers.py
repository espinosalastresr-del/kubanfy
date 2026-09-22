"""Built-in job handlers. Import this module to register handlers."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.models.job import Job, JobType
from app.workers.runner import register_handler

logger = get_logger(__name__)


@register_handler(JobType.GENERIC)
async def handle_generic(job: Job, session: Any) -> dict[str, Any] | None:
    logger.info("generic_job_executed", job_id=str(job.id), payload=job.payload)
    return {"ok": True}


@register_handler(JobType.NOTIFICATION)
async def handle_notification(job: Job, session: Any) -> dict[str, Any] | None:
    # Skeleton: real NotificationService will send email/in-app later
    logger.info(
        "notification_job",
        job_id=str(job.id),
        channel=job.payload.get("channel"),
        template=job.payload.get("template"),
    )
    return {"notified": True}


@register_handler(JobType.CACHE_CLEANUP)
async def handle_cache_cleanup(job: Job, session: Any) -> dict[str, Any] | None:
    # Skeleton: CacheService will implement expiry/orphan cleanup
    logger.info("cache_cleanup_job", job_id=str(job.id))
    return {"cleaned": 0}
