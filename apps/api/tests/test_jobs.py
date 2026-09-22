"""Unit tests for job types and handler registry."""

from __future__ import annotations

from app.models.job import JobStatus, JobType
from app.workers import handlers  # noqa: F401 — register handlers
from app.workers.runner import _handlers


def test_job_statuses() -> None:
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.DEAD_LETTER.value == "dead_letter"


def test_job_types_cover_plan() -> None:
    required = {
        "provider_acquisition",
        "transfer",
        "transcode",
        "cache_cleanup",
        "analytics",
        "ranking",
        "artist_upload",
        "notification",
    }
    actual = {t.value for t in JobType}
    assert required.issubset(actual)


def test_handlers_registered() -> None:
    assert JobType.GENERIC in _handlers
    assert JobType.NOTIFICATION in _handlers
    assert JobType.CACHE_CLEANUP in _handlers
