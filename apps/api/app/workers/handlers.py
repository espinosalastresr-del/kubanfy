"""Built-in job handlers. Import this module to register handlers."""

from __future__ import annotations

import struct
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
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
from app.services.kby_v2 import pack as pack_v2
from app.services.job import JobService
from app.storage import StorageBucket, get_storage
from app.workers.runner import register_handler

logger = get_logger(__name__)


def _is_fragmented_mp4(data: bytes) -> bool:
    boxes: set[str] = set()
    offset = 0
    while offset + 8 <= len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8].decode("ascii", "replace")
        header_size = 8
        if size == 1:
            if offset + 16 > len(data):
                return False
            size = struct.unpack(">Q", data[offset + 8 : offset + 16])[0]
            header_size = 16
        elif size == 0:
            size = len(data) - offset
        if size < header_size or offset + size > len(data):
            return False
        boxes.add(kind)
        offset += size
    return {"ftyp", "moov", "moof", "mdat"}.issubset(boxes)


@register_handler(JobType.GENERIC)
async def handle_generic(job: Job, session: Any) -> dict[str, Any] | None:
    if job.payload.get("action") != "backfill_kby2":
        logger.info("generic_job_executed", job_id=str(job.id), payload=job.payload)
        return {"ok": True}

    cursor = job.payload.get("cursor")
    batch_size = max(1, min(int(job.payload.get("batch_size", 20)), 50))
    stmt = (
        select(AudioAsset)
        .where(
            AudioAsset.is_active.is_(True),
            AudioAsset.storage_key.like("%.kby"),
            AudioAsset.source_type == SourceType.DERIVATIVE,
            AudioAsset.quality.in_([AudioQuality.LOW, AudioQuality.MEDIUM]),
            AudioAsset.quality_confidence == QualityConfidence.VERIFIED,
            AudioAsset.content_hash.is_not(None),
        )
        .order_by(AudioAsset.id.asc())
        .limit(batch_size)
    )
    if cursor:
        stmt = stmt.where(AudioAsset.id > UUID(cursor))
    assets = list((await session.scalars(stmt)).all())
    if not assets:
        return {"action": "backfill_kby2", "complete": True, "created": 0, "failed": 0}

    settings = get_settings()
    storage = get_storage()
    created = skipped = failed = 0
    for asset in assets:
        source_key = asset.storage_key
        target_key = source_key.rsplit(".kby", 1)[0] + ".kby2"
        if await storage.exists(target_key, bucket=StorageBucket.PERMANENT):
            skipped += 1
            continue
        container = await storage.get(source_key, bucket=StorageBucket.PERMANENT)
        try:
            encryption_key = derive_key(asset.content_hash, settings=settings)
            header, plaintext = unpack(
                container,
                key=encryption_key,
                expected_content_hash=asset.content_hash,
            )
            if header.quality != asset.quality.value:
                raise ValueError(
                    f"quality mismatch: container={header.quality} db={asset.quality.value}"
                )
            if asset.quality.value in {"low", "medium"} and not _is_fragmented_mp4(plaintext):
                raise ValueError("LOW/MEDIUM asset is not fragmented MP4")
        except Exception as exc:
            failed += 1
            logger.exception(
                "kby2_backfill_asset_invalid",
                asset_id=str(asset.id),
                track_id=str(asset.track_id),
                error_type=type(exc).__name__,
            )
            continue

        body = pack_v2(
            plaintext,
            content_hash=asset.content_hash,
            quality=asset.quality.value,
            content_type=header.content_type,
            settings=settings,
        )
        await storage.put(
            target_key,
            body,
            bucket=StorageBucket.PERMANENT,
            content_type="application/vnd.kubanfy.kby2",
        )
        created += 1

    next_cursor = str(assets[-1].id)
    complete = len(assets) < batch_size
    if not complete:
        await JobService(session).enqueue(
            JobType.GENERIC,
            {
                "action": "backfill_kby2",
                "cursor": next_cursor,
                "batch_size": batch_size,
                "failed_total": int(job.payload.get("failed_total", 0)) + failed,
                "run_id": job.payload.get("run_id"),
            },
            correlation_id=job.correlation_id,
            idempotency_key=f"kby2-backfill:{job.payload.get('run_id', job.id)}:{next_cursor}",
        )
    result = {
        "action": "backfill_kby2",
        "complete": complete,
        "cursor": next_cursor,
        "processed": len(assets),
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "failed_total": int(job.payload.get("failed_total", 0)) + failed,
    }
    logger.info("kby2_backfill_batch_done", **result)
    return result


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
            kby2_body = pack_v2(
                body,
                content_hash=out.probe.content_hash,
                quality=quality.value,
                content_type="audio/mp4",
            )
            dest_key_v2 = dest_key.rsplit(".kby", 1)[0] + ".kby2"
            await storage.put(
                dest_key_v2,
                kby2_body,
                bucket=StorageBucket.PERMANENT,
                content_type="application/vnd.kubanfy.kby2",
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
