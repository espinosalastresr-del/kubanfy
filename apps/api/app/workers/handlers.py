"""Built-in job handlers. Import this module to register handlers."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.models.job import Job, JobType
from app.models.music import AudioAsset, AudioQuality, QualityConfidence, SourceType, Track, TrackStatus
from app.services.cache import CacheService
from app.services.transcoding import TranscodingService
from app.storage import StorageBucket, get_storage
from app.workers.runner import register_handler

logger = get_logger(__name__)


@register_handler(JobType.GENERIC)
async def handle_generic(job: Job, session: Any) -> dict[str, Any] | None:
    logger.info("generic_job_executed", job_id=str(job.id), payload=job.payload)
    return {"ok": True}


@register_handler(JobType.NOTIFICATION)
async def handle_notification(job: Job, session: Any) -> dict[str, Any] | None:
    logger.info(
        "notification_job",
        job_id=str(job.id),
        channel=job.payload.get("channel"),
        template=job.payload.get("template"),
    )
    return {"notified": True}


@register_handler(JobType.CACHE_CLEANUP)
async def handle_cache_cleanup(job: Job, session: Any) -> dict[str, Any] | None:
    cache = CacheService(session)
    expired = await cache.expire_stale(limit=int(job.payload.get("limit", 100)))
    purged = 0
    for entry in await cache.list_expired_for_purge(limit=int(job.payload.get("purge_limit", 50))):
        await cache.purge_entry(entry)
        purged += 1
    logger.info("cache_cleanup_done", expired=expired, purged=purged)
    return {"expired": expired, "purged": purged}


@register_handler(JobType.TRANSCODE)
async def handle_transcode(job: Job, session: Any) -> dict[str, Any] | None:
    """Generate LOW/MEDIUM derivatives from permanent master."""
    payload = job.payload
    track_id = UUID(payload["track_id"])
    master_key = payload["master_key"]
    qualities = payload.get("qualities") or ["low", "medium"]

    track = await session.get(Track, track_id)
    if track is None:
        logger.warning("transcode_track_missing", track_id=str(track_id))
        return {"skipped": True, "reason": "track_not_found"}

    storage = get_storage()
    master_bytes = await storage.get(master_key, bucket=StorageBucket.PERMANENT)

    transcoder = TranscodingService()
    produced: list[str] = []

    with tempfile.TemporaryDirectory(prefix="kubanfy-tx-") as tmp:
        master_path = Path(tmp) / "master.bin"
        master_path.write_bytes(master_bytes)

        for q_name in qualities:
            try:
                quality = AudioQuality(q_name)
            except ValueError:
                continue
            out = await transcoder.transcode_to_quality(master_path, quality, output_dir=tmp)
            body = out.path.read_bytes()
            dest_key = (
                f"artists/{payload.get('artist_id', 'unknown')}/tracks/{track_id}/"
                f"{quality.value}/{out.probe.content_hash[:16]}"
            )
            await storage.put(
                dest_key,
                body,
                bucket=StorageBucket.PERMANENT,
                content_type=f"audio/{out.codec}",
            )
            asset = AudioAsset(
                track_id=track_id,
                storage_key=dest_key,
                codec=out.probe.codec or out.codec,
                bitrate=out.bitrate_kbps,
                bit_depth=out.probe.bit_depth,
                sample_rate=out.probe.sample_rate,
                channels=out.probe.channels,
                duration=out.probe.duration,
                size=out.probe.size,
                quality=quality,
                quality_confidence=QualityConfidence.VERIFIED,
                source_type=SourceType.DERIVATIVE,
                content_hash=out.probe.content_hash,
            )
            session.add(asset)
            produced.append(quality.value)

        await session.flush()

    # Move track out of processing if it was waiting
    if track.status == TrackStatus.PROCESSING:
        track.status = TrackStatus.DRAFT
        await session.flush()

    logger.info("transcode_job_done", track_id=str(track_id), qualities=produced)
    return {"track_id": str(track_id), "qualities": produced}
