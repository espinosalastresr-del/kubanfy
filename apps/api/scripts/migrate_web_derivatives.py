"""Migrate active LOW/MEDIUM catalog derivatives to web-ready fMP4.

This is a controlled migration. It creates a new asset generation for each
non-fMP4 active derivative, activates the new generation only after the new
KBY v1 + KBY2 objects are stored, and leaves old objects available for
previously issued offline licenses.

Run from apps/api:
    python -m scripts.migrate_web_derivatives --dry-run
    python -m scripts.migrate_web_derivatives --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import tempfile
from contextlib import suppress
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory, close_db, init_db
from app.core.exceptions import ValidationError
from app.models.music import AudioAsset, AudioQuality, QualityConfidence, SourceType, Track
from app.services.audio_validation import AudioValidationService
from app.services.kby import derive_key, unpack as unpack_v1
from app.services.kby import pack as pack_v1
from app.services.kby_v2 import pack as pack_v2
from app.services.transcoding import TranscodingService
from app.storage import StorageBucket, get_storage


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

            assets = (await session.scalars(stmt)).all()
            migrated = skipped = failed = 0

            for asset in assets:
                track = await session.get(Track, asset.track_id)
                if track is None:
                    failed += 1
                    print(f"FAILED {asset.track_id}: track missing")
                    continue

                try:
                    assert asset.storage_key is not None
                    assert asset.content_hash is not None

                    source_key = asset.storage_key
                    kby2_key = source_key.rsplit(".kby", 1)[0] + ".kby2"
                    if await storage.exists(kby2_key, bucket=StorageBucket.PERMANENT):
                        container = await storage.get(kby2_key, bucket=StorageBucket.PERMANENT)
                        _, existing_plaintext = unpack_v1(
                            await storage.get(source_key, bucket=StorageBucket.PERMANENT),
                            key=derive_key(asset.content_hash, settings=settings),
                            expected_content_hash=asset.content_hash,
                        )
                        if b"moof" in existing_plaintext:
                            skipped += 1
                            print(f"SKIP    {track.id} {asset.quality.value}: already appears fragmented")
                            continue

                    # Prefer the current lossless master as the migration source.
                    source = await session.scalar(
                        select(AudioAsset)
                        .where(
                            AudioAsset.track_id == asset.track_id,
                            AudioAsset.is_active.is_(True),
                            AudioAsset.quality == AudioQuality.LOSSLESS,
                            AudioAsset.storage_key.like("%.kby"),
                            AudioAsset.content_hash.is_not(None),
                        )
                        .order_by(AudioAsset.version.desc())
                    )
                    if source is None:
                        source = await session.scalar(
                            select(AudioAsset)
                            .where(
                                AudioAsset.track_id == asset.track_id,
                                AudioAsset.is_active.is_(True),
                                AudioAsset.storage_key.like("%.kby"),
                                AudioAsset.content_hash.is_not(None),
                            )
                            .order_by(AudioAsset.quality.desc(), AudioAsset.version.desc())
                        )
                    if source is None or not source.storage_key or not source.content_hash:
                        raise ValidationError("no active source asset available")

                    source_plaintext = await storage.get(
                        source.storage_key, bucket=StorageBucket.PERMANENT
                    )
                    _, source_bytes = unpack_v1(
                        source_plaintext,
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

                        if track.duration is not None and output.probe.duration is not None:
                            tolerance = max(2.0, float(track.duration) * 0.02)
                            if abs(float(track.duration) - float(output.probe.duration)) > tolerance:
                                raise ValidationError(
                                    f"duration mismatch: track={track.duration} output={output.probe.duration}"
                                )

                        await validator.validate_for_storage(output.path)
                        derivative_bytes = output.path.read_bytes()
                        content_hash = output.probe.content_hash

                        if dry_run:
                            print(
                                f"DRY-RUN {track.id} {asset.quality.value}: "
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
                        generation = f"v{next_version}"
                        key = (
                            f"artists/{asset.storage_key.split('/artists/', 1)[-1]}"
                            if False
                            else f"tracks/{asset.track_id}/{generation}/{asset.quality.value}/{content_hash[:16]}.kby"
                        )
                        # Keep the same permanent namespace used by first-party uploads.
                        key = (
                            f"artists/{track.release_id}/tracks/{asset.track_id}/"
                            f"{generation}/{asset.quality.value}/{content_hash[:16]}.kby"
                        )
                        # The release id is not the artist id; derive the artist id from
                        # the existing key instead of guessing it.
                        parts = asset.storage_key.split("/")
                        if len(parts) >= 2 and parts[0] == "artists":
                            artist_id = parts[1]
                            key = (
                                f"artists/{artist_id}/tracks/{asset.track_id}/{generation}/"
                                f"{asset.quality.value}/{content_hash[:16]}.kby"
                            )

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
                        kby2_key = key.rsplit(".kby", 1)[0] + ".kby2"

                        await storage.put(
                            key, kby, bucket=StorageBucket.PERMANENT,
                            content_type="application/vnd.kubanfy.kby",
                        )
                        await storage.put(
                            kby2_key, kby2, bucket=StorageBucket.PERMANENT,
                            content_type="application/vnd.kubanfy.kby2",
                        )

                        new_asset = AudioAsset(
                            track_id=asset.track_id,
                            storage_key=key,
                            codec=output.probe.codec,
                            bitrate=output.probe.bitrate // 1000 if output.probe.bitrate else None,
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
                        await session.flush()
                        migrated += 1
                        print(f"MIGRATED {asset.track_id} {asset.quality.value} -> {key}")

                except Exception as exc:
                    failed += 1
                    await session.rollback()
                    print(f"FAILED {asset.track_id} {asset.quality.value}: {type(exc).__name__}: {exc}")

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
