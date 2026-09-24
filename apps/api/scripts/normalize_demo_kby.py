"""Convert the development demo asset to the real KBY storage format.

This script is staging/development fixture setup only. Playback itself still
uses the normal catalog authorization -> signed URL -> KBY decryption path.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import async_session_factory, close_db, init_db
from app.core.config import get_settings
from app.models.music import AudioAsset, Track
from app.services.kby import pack
from app.storage import StorageBucket, get_storage


async def main() -> None:
    settings = get_settings()
    init_db(settings)
    if async_session_factory is None:
        raise RuntimeError("DB not initialized")

    async with async_session_factory() as session:
        track = await session.scalar(
            select(Track).where(Track.slug == "kubanfy-connectivity-test")
        )
        if track is None:
            print("No demo track found; nothing to normalize.")
            return

        storage = get_storage()
        assets = list(
            (
                await session.scalars(
                    select(AudioAsset).where(
                        AudioAsset.track_id == track.id,
                        AudioAsset.is_active.is_(True),
                    )
                )
            ).all()
        )

        for asset in assets:
            if asset.storage_key.endswith(".kby"):
                continue
            plaintext = await storage.get(
                asset.storage_key,
                bucket=StorageBucket.PERMANENT,
            )
            content_hash = asset.content_hash or hashlib.sha256(plaintext).hexdigest()
            kby = pack(
                plaintext,
                content_hash=content_hash,
                quality=asset.quality.value,
                content_type="audio/wav" if asset.storage_key.endswith(".wav") else "audio/mpeg",
                settings=settings,
            )
            new_key = asset.storage_key.rsplit(".", 1)[0] + ".kby"
            await storage.put(
                new_key,
                kby,
                bucket=StorageBucket.PERMANENT,
                content_type="application/vnd.kubanfy.kby",
            )
            await storage.delete(asset.storage_key, bucket=StorageBucket.PERMANENT)
            asset.storage_key = new_key
            asset.content_hash = content_hash
            asset.size = len(kby)

        await session.commit()
        print(f"Normalized demo track to KBY: {track.id}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
