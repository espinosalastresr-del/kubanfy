"""Job creation, claiming, retry, and completion.

Workers poll for PENDING/RETRYING jobs ordered by next_run_at.
Idempotency via unique idempotency_key.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.job import Job, JobStatus, JobType

logger = get_logger(__name__)


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        job_type: JobType | str,
        payload: dict[str, Any] | None = None,
        *,
        max_attempts: int = 5,
        run_at: datetime | None = None,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Job:
        if isinstance(job_type, str):
            job_type = JobType(job_type)

        if idempotency_key:
            existing = await self.session.scalar(
                select(Job).where(Job.idempotency_key == idempotency_key)
            )
            if existing is not None:
                logger.info(
                    "job_idempotent_hit",
                    job_id=str(existing.id),
                    key=idempotency_key,
                )
                return existing

        job = Job(
            type=job_type,
            status=JobStatus.PENDING,
            payload=payload or {},
            max_attempts=max_attempts,
            next_run_at=run_at or datetime.now(UTC),
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        self.session.add(job)
        try:
            await self.session.flush()
        except Exception:
            # Unique constraint on idempotency_key under race
            if idempotency_key:
                await self.session.rollback()
                existing = await self.session.scalar(
                    select(Job).where(Job.idempotency_key == idempotency_key)
                )
                if existing:
                    return existing
            raise

        logger.info(
            "job_enqueued",
            job_id=str(job.id),
            type=job.type.value,
            correlation_id=correlation_id,
        )
        return job

    async def claim_next(
        self,
        *,
        types: list[JobType] | None = None,
        worker_id: str | None = None,
    ) -> Job | None:
        """Atomically claim the next runnable job (FOR UPDATE SKIP LOCKED)."""
        now = datetime.now(UTC)
        q = (
            select(Job)
            .where(
                Job.status.in_([JobStatus.PENDING, JobStatus.RETRYING]),
                Job.next_run_at <= now,
            )
            .order_by(Job.next_run_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if types:
            q = q.where(Job.type.in_(types))

        result = await self.session.execute(q)
        job = result.scalar_one_or_none()
        if job is None:
            return None

        job.status = JobStatus.RUNNING
        job.attempts += 1
        job.started_at = now
        job.error = None
        await self.session.flush()
        logger.info(
            "job_claimed",
            job_id=str(job.id),
            type=job.type.value,
            attempt=job.attempts,
            worker_id=worker_id,
        )
        return job

    async def complete(self, job_id: UUID, *, result: dict[str, Any] | None = None) -> Job:
        job = await self.session.get(Job, job_id)
        if job is None:
            raise NotFoundError("Job not found")
        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.now(UTC)
        if result is not None:
            job.payload = {**job.payload, "_result": result}
        await self.session.flush()
        logger.info("job_completed", job_id=str(job_id))
        return job

    async def fail(
        self,
        job_id: UUID,
        error: str,
        *,
        retry: bool = True,
        base_delay_seconds: float = 5.0,
    ) -> Job:
        job = await self.session.get(Job, job_id)
        if job is None:
            raise NotFoundError("Job not found")

        job.error = error[:4000]
        if retry and job.attempts < job.max_attempts:
            # Exponential backoff with jitter
            delay = base_delay_seconds * (2 ** (job.attempts - 1))
            delay = min(delay, 3600)  # cap 1h
            delay *= 0.5 + random.random()  # jitter
            job.status = JobStatus.RETRYING
            job.next_run_at = datetime.now(UTC) + timedelta(seconds=delay)
            job.finished_at = None
            logger.warning(
                "job_retrying",
                job_id=str(job_id),
                attempt=job.attempts,
                delay_s=round(delay, 1),
                error=error[:200],
            )
        else:
            job.status = JobStatus.DEAD_LETTER if job.attempts >= job.max_attempts else JobStatus.FAILED
            job.finished_at = datetime.now(UTC)
            logger.error(
                "job_failed",
                job_id=str(job_id),
                status=job.status.value,
                error=error[:200],
            )
        await self.session.flush()
        return job

    async def cancel(self, job_id: UUID) -> Job:
        job = await self.session.get(Job, job_id)
        if job is None:
            raise NotFoundError("Job not found")
        if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED):
            raise ConflictError(f"Cannot cancel job in status {job.status.value}")
        job.status = JobStatus.CANCELLED
        job.finished_at = datetime.now(UTC)
        await self.session.flush()
        logger.info("job_cancelled", job_id=str(job_id))
        return job

    async def get(self, job_id: UUID) -> Job | None:
        return await self.session.get(Job, job_id)

    async def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 50,
    ) -> list[Job]:
        q = select(Job).order_by(Job.created_at.desc()).limit(limit)
        if status:
            q = q.where(Job.status == status)
        if job_type:
            q = q.where(Job.type == job_type)
        result = await self.session.execute(q)
        return list(result.scalars().all())
