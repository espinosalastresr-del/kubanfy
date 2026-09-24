"""Built-in job handlers. Import this module to register handlers."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.logging import get_logger
from app.models.job import Job, JobType
from app.models.music import (
    AudioAsset,
    AudioQuality,
    QualityConfidence,
    Release,
    SourceType,
    Track,
    TrackStatus,
)
from app.services.cache import CacheService
from app.services.transcoding import TranscodingService
from app.services.kby import derive_key, pack, unpack
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


@register_handler(JobType.PUBLICATION_SCHEDULE)
async def handle_publication_schedule(job: Job, session: Any) -> dict[str, Any] | None:
    payload = job.payload
    release = await session.get(Release, UUID(payload["release_id"]))
    if release is None or release.status == TrackStatus.DELETED:
        return {"skipped": True, "reason": "release_not_found_or_deleted"}

    scheduled_at = datetime.fromisoformat(payload["scheduled_at"])
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=UTC)
    else:
        scheduled_at = scheduled_at.astimezone(UTC)

    action = payload.get("action")
    if action == "publish":
        current = release.scheduled_publish_at
        if current is None:
            return {"skipped": True, "reason": "schedule_superseded"}
        current = current.replace(tzinfo=UTC) if current.tzinfo is None else current.astimezone(UTC)
        if current != scheduled_at:
            return {"skipped": True, "reason": "schedule_superseded"}
        tracks = list(
            (await session.scalars(select(Track).where(Track.release_id == release.id))).all()
        )
        if not tracks:
            return {"skipped": True, "reason": "release_has_no_tracks"}
        if any(t.status != TrackStatus.PUBLISHED for t in tracks):
            return {"skipped": True, "reason": "tracks_not_published"}
        release.status = TrackStatus.PUBLISHED
        release.scheduled_publish_at = None
        await session.flush()
        return {"published": True, "release_id": str(release.id)}

    if action == "unpublish":
        current = release.scheduled_unpublish_at
        if current is None:
            return {"skipped": True, "reason": "schedule_superseded"}
        current = current.replace(tzinfo=UTC) if current.tzinfo is None else current.astimezone(UTC)
        if current != scheduled_at:
            return {"skipped": True, "reason": "schedule_superseded"}
        release.status = TrackStatus.HIDDEN
        release.scheduled_unpublish_at = None
        await session.execute(
            Track.__table__.update()
            .where(Track.release_id == release.id, Track.status == TrackStatus.PUBLISHED)
            .values(status=TrackStatus.HIDDEN)
        )
        await session.flush()
        return {"unpublished": True, "release_id": str(release.id)}

    return {"skipped": True, "reason": "invalid_action"}


@register_handler(JobType.TRANSCODE)
async def handle_transcode(job: Job, session: Any) -> dict[str, Any] | None:
    """Generate LOW/MEDIUM derivatives from permanent master.

    The handler is retry-safe: each derivative is identified by the master
    asset version and quality, so a partially completed attempt can resume
    without creating duplicate AudioAsset rows.
    """
    payload = job.payload
    track_id = UUID(payload["track_id"])
    master_key = payload["master_key"]
    qualities = payload.get("qualities") or ["low", "medium"]

    track = await session.get(Track, track_id)
    if track is None:
        logger.warning("transcode_track_missing", track_id=str(track_id))
        return {"skipped": True, "reason": "track_not_found"}

    master_asset = await session.scalar(
        select(AudioAsset)
        .where(
            AudioAsset.track_id == track_id,
            AudioAsset.storage_key == master_key,
            AudioAsset.source_type == SourceType.ARTIST_UPLOAD,
        )
        .order_by(AudioAsset.version.desc())
    )
    if master_asset is None:
        raise ValueError("Transcode master asset not found")

    storage = get_storage()
    master_bytes = await storage.get(master_key, bucket=StorageBucket.PERMANENT)
    if not master_asset.content_hash:
        raise ValueError("Transcode master asset is missing content hash")
    _, plaintext_master = unpack(
        master_bytes,
        key=derive_key(master_asset.content_hash),
        expected_content_hash=master_asset.content_hash,
    )

    transcoder = TranscodingService()
    produced: list[str] = []
    skipped: list[str] = []

    with tempfile.TemporaryDirectory(prefix="kubanfy-tx-") as tmp:
        master_path = Path(tmp) / "master.bin"
        master_path.write_bytes(plaintext_master)

        for q_name in qualities:
            try:
                quality = AudioQuality(q_name)
            except ValueError:
                continue

            existing = await session.scalar(
                select(AudioAsset)
                .where(
                    AudioAsset.track_id == track_id,
                    AudioAsset.quality == quality,
                    AudioAsset.version == master_asset.version,
                    AudioAsset.source_type == SourceType.DERIVATIVE,
                    AudioAsset.is_active.is_(True),
                )
                .limit(1)
            )
            if existing is not None:
                skipped.append(quality.value)
                continue

            out = await transcoder.transcode_to_quality(master_path, quality, output_dir=tmp)
            body = out.path.read_bytes()
            dest_key = (
                f"artists/{payload.get('artist_id', 'unknown')}/tracks/{track_id}/"
                f"v{master_asset.version}/{quality.value}/{out.probe.content_hash[:16]}.kby"
            )
            kby_body = pack(
                body,
                content_hash=out.probe.content_hash,
                quality=quality.value,
                content_type="audio/mp4",
            )
            await storage.put(
                dest_key,
                kby_body,
                bucket=StorageBucket.PERMANENT,
                content_type="application/vnd.kubanfy.kby",
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
                size=len(kby_body),
                quality=quality,
                quality_confidence=QualityConfidence.VERIFIED,
                source_type=SourceType.DERIVATIVE,
                content_hash=out.probe.content_hash,
                version=master_asset.version,
                is_active=True,
            )
            session.add(asset)
            produced.append(quality.value)

        await session.flush()

    if track.status == TrackStatus.PROCESSING:
        track.status = TrackStatus.DRAFT
        await session.flush()

    logger.info(
        "transcode_job_done",
        track_id=str(track_id),
        produced=produced,
        skipped=skipped,
        version=master_asset.version,
    )
    return {
        "track_id": str(track_id),
        "version": master_asset.version,
        "qualities": produced,
        "skipped": skipped,
    }
