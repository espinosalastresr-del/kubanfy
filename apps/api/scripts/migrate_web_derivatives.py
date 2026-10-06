"""Migrate active LOW/MEDIUM derivatives to web-ready fragmented MP4.

The migration is intentionally controlled. It creates a new asset generation,
stores KBY v1 and KBY2, commits that generation, and only then deactivates the
old active derivative. Old objects remain available for already-issued
offline licenses.

Run from apps/api:
    python -m scripts.migrate_web_derivatives --dry-run
    python -m scripts.migrate_web_derivatives --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import tempfile
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory, close_db, init_db
from app.core.exceptions import ValidationError
from app.models.music import AudioAsset, AudioQuality, QualityConfidence, SourceType, Track
from app.services.audio_validation import AudioValidationService
from app.services.kby import derive_key, pack as pack_v1, unpack as unpack_v1
from app.services.kby_v2 import pack as pack_v2
from app.services.transcoding import TranscodingService
from app.storage import StorageBucket, get_storage
from scripts.audit_web_assets import _is_fragmented_mp4


def _artist_id_from_storage_key(storage_key: str) -> str:
    parts = storage_key.split("/")
    if len(parts) < 2 or parts[0] != "artists" or not parts[1]:
        raise ValidationError("Cannot derive artist id from asset storage key")
    return parts[1]


async def run(*, limit: int | None, dry_run: bool) -> None:
    settings = get_settings()
    init_db(settings)
    try:
        assert async_session_factory is not None
        storage = get_storage()
        transcoder = TranscodingService(settings)
        validator = AudioValidationService(settings)

        async with async_session_factory() as session:
            stmt = (
                select(AudioAsset)
                .where(
                    AudioAsset.is_active.is_(True),
                    AudioAsset.quality.in_([AudioQuality.LOW, AudioQuality.MEDIUM]),
                    AudioAsset.storage_key.like("%.kby"),
                    AudioAsset.content_hash.is_not(None),
                )
                .order_by(AudioAsset.created_at, AudioAsset.id)
            )
            if limit:
                stmt = stmt.limit(limit)

            assets = list((await session.scalars(stmt)).all())
            migrated = skipped = failed = 0

            for asset in assets:
                try:
                    if not asset.storage_key or not asset.content_hash:
                        raise ValidationError("active derivative is incomplete")

                    source_kby = await storage.get(
                        asset.storage_key,
                        bucket=StorageBucket.PERMANENT,
                    )
                    _, current_plaintext = unpack_v1(
                        source_kby,
                        key=derive_key(asset.content_hash, settings=settings),
                        expected_content_hash=asset.content_hash,
                    )

                    target_kby2 = asset.storage_key.rsplit(".kby", 1)[0] + ".kby2"
                    if (
                        await storage.exists(target_kby2, bucket=StorageBucket.PERMANENT)
                        and _is_fragmented_mp4(current_plaintext)
                    ):
                        skipped += 1
                        print(f"SKIP {asset.track_id} {asset.quality.value} v{asset.version}")
                        continue

                    track = await session.get(Track, asset.track_id)
                    if track is None or track.status.value != "published":
                        raise ValidationError("track is missing or not published")

                    active_assets = list(
                        (
                            await session.scalars(
                                select(AudioAsset).where(
                                    AudioAsset.track_id == asset.track_id,
                                    AudioAsset.is_active.is_(True),
                                    AudioAsset.storage_key.like("%.kby"),
                                    AudioAsset.content_hash.is_not(None),
                                )
                            )
                        ).all()
                    )
                    sources = [
                        a
                        for a in active_assets
                        if a.quality == AudioQuality.LOSSLESS
                    ]
                    if not sources:
                        sources = [
                            a
                            for a in active_assets
                            if a.quality in {AudioQuality.MEDIUM, AudioQuality.LOW}
                            and a.id != asset.id
                        ]
                    if not sources:
                        raise ValidationError("no active source asset available")
                    source = max(sources, key=lambda a: a.version)

                    source_container = await storage.get(
                        source.storage_key,
                        bucket=StorageBucket.PERMANENT,
                    )
                    _, source_bytes = unpack_v1(
                        source_container,
                        key=derive_key(source.content_hash, settings=settings),
                        expected_content_hash=source.content_hash,
                    )

                    with tempfile.TemporaryDirectory(prefix="kubanfy-web-migrate-") as tmp:
                        source_path = Path(tmp) / "source.bin"
                        source_path.write_bytes(source_bytes)
                        output = await transcoder.transcode_to_quality(
                            source_path,
                            asset.quality,
                            output_dir=Path(tmp) / "out",
                        )
                        await validator.validate_for_storage(output.path)

                        if track.duration is not None and output.probe.duration is not None:
                            tolerance = max(2.0, float(track.duration) * 0.02)
                            if abs(float(track.duration) - float(output.probe.duration)) > tolerance:
                                raise ValidationError(
                                    f"duration mismatch: track={track.duration} "
                                    f"output={output.probe.duration}"
                                )

                        derivative_bytes = output.path.read_bytes()
                        if not _is_fragmented_mp4(derivative_bytes):
                            raise ValidationError("FFmpeg output is not fragmented MP4")

                        if dry_run:
                            print(
                                f"DRY-RUN {asset.track_id} {asset.quality.value}: "
                                f"{len(derivative_bytes)} plaintext bytes"
                            )
                            migrated += 1
                            continue

                        max_version = await session.scalar(
                            select(AudioAsset.version)
                            .where(AudioAsset.track_id == asset.track_id)
                            .order_by(AudioAsset.version.desc())
                            .limit(1)
                        )
                        next_version = int(max_version or 0) + 1
                        content_hash = output.probe.content_hash
                        artist_id = _artist_id_from_storage_key(asset.storage_key)
                        key = (
                            f"artists/{artist_id}/tracks/{asset.track_id}/v{next_version}/"
                            f"{asset.quality.value}/{content_hash[:16]}.kby"
                        )
                        kby2_key = key.rsplit(".kby", 1)[0] + ".kby2"

                        kby = pack_v1(
                            derivative_bytes,
                            content_hash=content_hash,
                            quality=asset.quality.value,
                            content_type="audio/mp4",
                            settings=settings,
                        )
                        kby2 = pack_v2(
                            derivative_bytes,
                            content_hash=content_hash,
                            quality=asset.quality.value,
                            content_type="audio/mp4",
                            settings=settings,
                        )
                        await storage.put(
                            key,
                            kby,
                            bucket=StorageBucket.PERMANENT,
                            content_type="application/vnd.kubanfy.kby",
                        )
                        await storage.put(
                            kby2_key,
                            kby2,
                            bucket=StorageBucket.PERMANENT,
                            content_type="application/vnd.kubanfy.kby2",
                        )

                        new_asset = AudioAsset(
                            track_id=asset.track_id,
                            storage_key=key,
                            codec=output.probe.codec,
                            bitrate=(
                                output.probe.bitrate // 1000
                                if output.probe.bitrate
                                else None
                            ),
                            sample_rate=output.probe.sample_rate,
                            channels=output.probe.channels,
                            duration=output.probe.duration,
                            size=len(kby),
                            quality=asset.quality,
                            quality_confidence=QualityConfidence.VERIFIED,
                            source_type=SourceType.DERIVATIVE,
                            content_hash=content_hash,
                            version=next_version,
                            is_active=True,
                        )
                        session.add(new_asset)
                        asset.is_active = False
                        await session.commit()
                        migrated += 1
                        print(f"MIGRATED {asset.track_id} {asset.quality.value} -> {key}")

                except Exception as exc:
                    await session.rollback()
                    failed += 1
                    print(
                        f"FAILED {asset.track_id} {asset.quality.value}: "
                        f"{type(exc).__name__}: {exc}"
                    )

            print(
                f"Summary: total={len(assets)} migrated={migrated} "
                f"skipped={skipped} failed={failed}"
            )
            if failed:
                raise RuntimeError(f"{failed} web derivative migrations failed")
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
