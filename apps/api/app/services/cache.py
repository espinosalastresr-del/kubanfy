"""Cache service for audio assets.

DB is source of truth for expires_at.
Redis single-flight prevents stampede on cache miss.
R2 lifecycle is only a safety net.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.audio_validation import AudioValidationService
from app.services.kby import pack
from app.models.music import AudioQuality, CacheEntry, CacheEntryStatus
from app.storage import StorageBucket, get_storage
from app.storage.base import SignedUrl, StorageProvider

logger = get_logger(__name__)


class CacheService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: StorageProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.storage = storage or get_storage()
        self.settings = settings or get_settings()

    def _ttl_hours(self, demand: str = "medium") -> int:
        if demand == "low":
            return self.settings.cache_ttl_low_demand_hours
        if demand == "high":
            return self.settings.cache_ttl_high_demand_hours
        return self.settings.cache_ttl_medium_demand_hours

    async def lookup(
        self,
        *,
        provider: str,
        provider_track_id: str,
        quality: AudioQuality,
    ) -> CacheEntry | None:
        now = datetime.now(UTC)
        entry = await self.session.scalar(
            select(CacheEntry).where(
                CacheEntry.provider == provider,
                CacheEntry.provider_track_id == provider_track_id,
                CacheEntry.quality == quality,
                CacheEntry.status == CacheEntryStatus.READY,
                CacheEntry.storage_key.like("%.kby"),
                CacheEntry.expires_at > now,
            )
        )
        return entry

    async def touch(self, entry: CacheEntry) -> None:
        entry.last_accessed_at = datetime.now(UTC)
        entry.access_count = (entry.access_count or 0) + 1
        entry.requests_24h = (entry.requests_24h or 0) + 1
        entry.requests_7d = (entry.requests_7d or 0) + 1
        # Simple retention score: accesses + recency bias
        entry.retention_score = float(entry.access_count) + entry.requests_7d * 0.5
        await self.session.flush()

    async def signed_delivery(self, entry: CacheEntry) -> SignedUrl:
        await self.touch(entry)
        return await self.storage.signed_url(
            entry.storage_key,
            bucket=StorageBucket.CACHE,
        )

    async def store_bytes(
        self,
        *,
        provider: str,
        provider_track_id: str,
        quality: AudioQuality,
        body: bytes,
        track_id: UUID | None = None,
        content_type: str = "audio/mpeg",
        demand: str = "medium",
        content_hash: str | None = None,
    ) -> CacheEntry:
        suffix = {
            "audio/flac": ".flac",
            "audio/mp4": ".m4a",
            "audio/mpeg": ".mp3",
            "audio/ogg": ".ogg",
            "audio/opus": ".opus",
            "audio/wav": ".wav",
        }.get(content_type.lower(), ".bin")
        probe = await AudioValidationService(self.settings).validate_bytes(
            bytes(body),
            suffix=suffix,
        )
        if content_hash is not None and content_hash != probe.content_hash:
            raise ValueError("Acquired audio content hash mismatch")
        content_hash = probe.content_hash
        kby_body = pack(
            bytes(body),
            content_hash=content_hash,
            quality=quality.value,
            content_type=content_type,
            settings=self.settings,
        )
        storage_key = f"cache/{provider}/{provider_track_id}/{quality.value}/{content_hash[:16]}.kby"

        await self.storage.put(
            storage_key,
            kby_body,
            bucket=StorageBucket.CACHE,
            content_type="application/vnd.kubanfy.kby",
        )

        expires_at = datetime.now(UTC) + timedelta(hours=self._ttl_hours(demand))

        # Upsert-like: if same key exists, refresh
        existing = await self.session.scalar(
            select(CacheEntry).where(
                CacheEntry.provider == provider,
                CacheEntry.provider_track_id == provider_track_id,
                CacheEntry.quality == quality,
                CacheEntry.content_hash == content_hash,
            )
        )
        if existing:
            existing.storage_key = storage_key
            existing.size = len(kby_body)
            existing.expires_at = expires_at
            existing.status = CacheEntryStatus.READY
            existing.last_accessed_at = datetime.now(UTC)
            await self.session.flush()
            return existing

        entry = CacheEntry(
            content_hash=content_hash,
            track_id=track_id,
            provider=provider,
            provider_track_id=provider_track_id,
            quality=quality,
            storage_key=storage_key,
            size=len(kby_body),
            expires_at=expires_at,
            status=CacheEntryStatus.READY,
        )
        self.session.add(entry)
        await self.session.flush()
        logger.info(
            "cache_stored",
            provider=provider,
            provider_track_id=provider_track_id,
            quality=quality.value,
            size=len(kby_body),
        )
        return entry

    async def mark_processing(
        self,
        *,
        provider: str,
        provider_track_id: str,
        quality: AudioQuality,
    ) -> CacheEntry:
        """Placeholder row while single-flight acquisition runs."""
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self.settings.cache_single_flight_timeout_seconds + 60
        )
        entry = CacheEntry(
            provider=provider,
            provider_track_id=provider_track_id,
            quality=quality,
            storage_key=f"processing/{provider}/{provider_track_id}/{quality.value}",
            expires_at=expires_at,
            status=CacheEntryStatus.PROCESSING,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def expire_stale(self, *, limit: int = 100) -> int:
        """Mark expired entries. Physical R2 delete is handled by cleanup worker."""
        now = datetime.now(UTC)
        result = await self.session.execute(
            update(CacheEntry)
            .where(
                CacheEntry.status == CacheEntryStatus.READY,
                CacheEntry.expires_at <= now,
            )
            .values(status=CacheEntryStatus.EXPIRED)
            .execution_options(synchronize_session=False)
        )
        await self.session.flush()
        count = result.rowcount or 0
        if count:
            logger.info("cache_expired_marked", count=count)
        return count

    async def list_expired_for_purge(self, *, limit: int = 50) -> list[CacheEntry]:
        result = await self.session.execute(
            select(CacheEntry)
            .where(CacheEntry.status == CacheEntryStatus.EXPIRED)
            .order_by(CacheEntry.expires_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def purge_entry(self, entry: CacheEntry) -> None:
        try:
            await self.storage.delete(entry.storage_key, bucket=StorageBucket.CACHE)
        except Exception as exc:
            logger.warning("cache_r2_delete_failed", key=entry.storage_key, error=str(exc))
        await self.session.delete(entry)
        await self.session.flush()

    async def get_or_acquire(
        self,
        *,
        provider: str,
        provider_track_id: str,
        quality: AudioQuality,
        acquire_fn: Any,
    ) -> tuple[CacheEntry, bool]:
        """
        Lookup cache; on miss run acquire_fn under single-flight.
        acquire_fn() must return bytes (audio body).
        Returns (entry, from_cache).
        """
        hit = await self.lookup(
            provider=provider,
            provider_track_id=provider_track_id,
            quality=quality,
        )
        if hit is not None:
            return hit, True

        sf_key = f"acquire:{provider}:{provider_track_id}:{quality.value}"

        async def _do() -> CacheEntry:
            # Re-check after lock
            again = await self.lookup(
                provider=provider,
                provider_track_id=provider_track_id,
                quality=quality,
            )
            if again is not None:
                return again
            body: bytes = await acquire_fn()
            if not isinstance(body, (bytes, bytearray)):
                raise TypeError("acquire_fn must return bytes")
            return await self.store_bytes(
                provider=provider,
                provider_track_id=provider_track_id,
                quality=quality,
                body=bytes(body),
            )

        try:
            from app.core.locks import single_flight

            entry = await single_flight(
                sf_key,
                _do,
                ttl_seconds=float(self.settings.cache_single_flight_timeout_seconds),
            )
            # If we got an entry that was already there, treat as cache hit for metrics
            from_cache = hit is not None
            return entry, from_cache
        except Exception:
            # Redis unavailable — fall back to direct acquire without single-flight
            logger.warning("single_flight_unavailable_fallback")
            body = await acquire_fn()
            entry = await self.store_bytes(
                provider=provider,
                provider_track_id=provider_track_id,
                quality=quality,
                body=bytes(body),
            )
            return entry, False

    async def lookup_by_track(self, *, track_id: UUID, quality: AudioQuality) -> CacheEntry | None:
        result = await self.session.execute(
            select(CacheEntry)
            .where(
                CacheEntry.track_id == track_id,
                CacheEntry.quality == quality,
                CacheEntry.status == CacheEntryStatus.READY,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()
