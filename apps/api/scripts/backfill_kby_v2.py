"""Backfill streaming-capable KBY v2 objects from existing KBY v1 assets.

Run from apps/api after database/storage credentials are configured:
    python -m scripts.backfill_kby_v2
    python -m scripts.backfill_kby_v2 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory, close_db, init_db
from app.models.music import AudioAsset
from app.services.kby import derive_key, unpack as unpack_v1
from app.services.kby_v2 import pack as pack_v2
from app.storage import StorageBucket, get_storage


async def run(*, limit: int | None, dry_run: bool) -> None:
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
                    AudioAsset.storage_key.is_not(None),
                    AudioAsset.storage_key.like("%.kby"),
                    AudioAsset.content_hash.is_not(None),
                )
                .order_by(AudioAsset.created_at, AudioAsset.id)
            )
            if limit:
                stmt = stmt.limit(limit)

            assets = (await session.scalars(stmt)).all()
            print(f"Found {len(assets)} active KBY v1 assets")

            created = skipped = failed = 0
            for asset in assets:
                source_key = asset.storage_key
                assert source_key is not None
                target_key = source_key.rsplit(".kby", 1)[0] + ".kby2"

                if await storage.exists(target_key, bucket=StorageBucket.PERMANENT):
                    skipped += 1
                    continue

                try:
                    container = await storage.get(
                        source_key,
                        bucket=StorageBucket.PERMANENT,
                    )
                    key = derive_key(asset.content_hash, settings=settings)
                    header, plaintext = unpack_v1(
                        container,
                        key=key,
                        expected_content_hash=asset.content_hash,
                    )
                    if header.quality != asset.quality.value:
                        raise ValueError(
                            f"quality mismatch: container={header.quality} db={asset.quality.value}"
                        )

                    if dry_run:
                        print(f"DRY-RUN {source_key} -> {target_key} ({len(plaintext)} bytes)")
                    else:
                        v2 = pack_v2(
                            plaintext,
                            content_hash=asset.content_hash,
                            quality=asset.quality.value,
                            content_type=header.content_type,
                            settings=settings,
                        )
                        await storage.put(
                            target_key,
                            v2,
                            bucket=StorageBucket.PERMANENT,
                            content_type="application/vnd.kubanfy.kby2",
                        )
                        print(f"CREATED {target_key} ({len(v2)} bytes)")
                    created += 1
                except Exception as exc:
                    failed += 1
                    print(f"FAILED {source_key}: {type(exc).__name__}: {exc}")

            print(f"Done: created={created} skipped={skipped} failed={failed}")
            if failed:
                raise RuntimeError(f"{failed} KBY v2 assets failed validation/backfill")
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
