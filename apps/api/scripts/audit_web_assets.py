"""Audit active catalog assets for protected web streaming readiness.

The audit is read-only. It verifies that active LOW/MEDIUM assets have a KBY2
object, decrypt cleanly, contain a fragmented MP4 (ftyp + moov + moof + mdat),
and match the database content hash/quality.

Run from apps/api:
    python -m scripts.audit_web_assets
    python -m scripts.audit_web_assets --limit 20
"""

from __future__ import annotations

import argparse
import asyncio
import struct

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory, close_db, init_db
from app.models.music import AudioAsset, AudioQuality
from app.services.kby import derive_key
from app.services.kby_v2 import parse_header, unpack
from app.storage import StorageBucket, get_storage


def _top_level_boxes(data: bytes) -> list[str]:
    """Return valid ISO-BMFF top-level box types without scanning arbitrary bytes."""
    boxes: list[str] = []
    offset = 0
    while offset + 8 <= len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        header_size = 8
        if size == 1:
            if offset + 16 > len(data):
                return boxes
            size = struct.unpack(">Q", data[offset + 8 : offset + 16])[0]
            header_size = 16
        elif size == 0:
            size = len(data) - offset
        if size < header_size or offset + size > len(data):
            return boxes
        boxes.append(kind.decode("ascii", "replace"))
        offset += size
    return boxes


def _is_fragmented_mp4(data: bytes) -> bool:
    boxes = _top_level_boxes(data)
    return "ftyp" in boxes and "moov" in boxes and "moof" in boxes and "mdat" in boxes


async def run(*, limit: int | None) -> None:
    settings = get_settings()
    init_db(settings)
    try:
        assert async_session_factory is not None
        storage = get_storage()
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
            ok = missing = invalid = 0

            for asset in assets:
                assert asset.storage_key is not None
                assert asset.content_hash is not None
                target_key = asset.storage_key.rsplit(".kby", 1)[0] + ".kby2"
                label = f"{asset.track_id} {asset.quality.value} v{asset.version}"

                if not await storage.exists(target_key, bucket=StorageBucket.PERMANENT):
                    missing += 1
                    print(f"MISSING {label}: {target_key}")
                    continue

                try:
                    container = await storage.get(target_key, bucket=StorageBucket.PERMANENT)
                    header, _ = parse_header(container)
                    if header.quality != asset.quality.value:
                        raise ValueError(
                            f"quality mismatch: kby2={header.quality} db={asset.quality.value}"
                        )
                    if header.content_hash != asset.content_hash:
                        raise ValueError("content hash mismatch between DB and KBY2")
                    _, plaintext = unpack(
                        container,
                        key=derive_key(asset.content_hash, settings=settings),
                        expected_content_hash=asset.content_hash,
                    )
                    if not _is_fragmented_mp4(plaintext):
                        raise ValueError("plaintext media is not fragmented MP4")
                    if (asset.codec or "").lower() != "aac":
                        raise ValueError(f"database codec is not AAC: {asset.codec!r}")
                    ok += 1
                    print(f"OK      {label}: {len(plaintext)} bytes")
                except Exception as exc:
                    invalid += 1
                    print(f"INVALID {label}: {type(exc).__name__}: {exc}")

            print(f"Summary: total={len(assets)} ok={ok} missing={missing} invalid={invalid}")
            if missing or invalid:
                raise RuntimeError("Web streaming asset audit failed")
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(run(limit=args.limit))


if __name__ == "__main__":
    main()
