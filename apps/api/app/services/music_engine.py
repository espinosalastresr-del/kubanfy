"""Music Engine — update / preview / download.

Does not talk to providers directly; uses ProviderManager.
Cache lookup before external acquisition. Single-flight on miss.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ProviderUnavailableError
from app.core.logging import get_logger
from app.models.music import (
    AudioQuality,
    CacheEntry,
    CacheEntryStatus,
    Provider,
    ProviderTrack,
    Track,
    TrackStatus,
)
from app.providers.base import ResolvedSource, TrackMetadata
from app.providers.registry import ProviderManager, create_default_registry
from app.services.cache import CacheService
from app.storage import StorageBucket, get_storage
from app.storage.base import SignedUrl, StorageProvider

logger = get_logger(__name__)


@dataclass
class TrackUpdateResult:
    """Result of engine.update() — metadata without forcing full audio acquisition."""

    title: str
    artists: list[str]
    album: str | None
    duration: float | None
    artwork: str | None
    release_date: str | None
    isrc: str | None
    track_id: UUID | None
    provider: str
    provider_track_id: str
    quality_capabilities: list[str] = field(default_factory=list)
    preview_available: bool = False
    resolution_ref: str | None = None  # internal ref e.g. "mock:mock-1"


@dataclass
class PreviewResult:
    source: ResolvedSource | None
    signed_url: SignedUrl | None = None
    from_cache: bool = False


@dataclass
class DownloadResult:
    signed_url: SignedUrl | None
    storage_key: str | None
    quality: str
    from_cache: bool
    track_id: UUID | None = None
    content_hash: str | None = None
    expires_at: datetime | None = None


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:200] or "track"


class MusicEngine:
    def __init__(
        self,
        session: AsyncSession,
        *,
        provider_manager: ProviderManager | None = None,
        storage: StorageProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.providers = provider_manager or ProviderManager(
            create_default_registry(include_mock=True)
        )
        self.storage = storage or get_storage()

    async def update(
        self,
        *,
        provider: str | None = None,
        provider_track_id: str | None = None,
        query: str | None = None,
    ) -> TrackUpdateResult:
        """Resolve internal representation of content without mandatory full download."""
        meta: TrackMetadata | None = None
        provider_name = provider

        if provider and provider_track_id:
            meta = await self.providers.get_track(provider, provider_track_id)
            provider_name = provider
        elif query:
            results = await self.providers.search(query, limit=1)
            if not results:
                raise NotFoundError("No tracks found for query")
            provider_name, meta = results[0]
            provider_track_id = meta.provider_track_id
        else:
            raise NotFoundError("provider+provider_track_id or query required")

        if meta is None or provider_name is None or provider_track_id is None:
            raise NotFoundError("Track metadata not found")

        # Ensure provider row exists
        db_provider = await self._ensure_provider(provider_name)

        # Link or create internal track
        track = await self._upsert_track_from_metadata(db_provider, meta)

        caps = []
        p = self.providers.registry.get(provider_name)
        if p:
            c = p.capabilities
            if c.audio:
                caps.append("audio")
            if c.lossless:
                caps.append("lossless")
            if c.preview:
                caps.append("preview")
            if c.hi_res:
                caps.append("hi_res")

        preview_available = False
        if p and p.capabilities.preview:
            preview_available = True

        return TrackUpdateResult(
            title=meta.title,
            artists=list(meta.artists),
            album=meta.album,
            duration=meta.duration_seconds,
            artwork=meta.artwork_url,
            release_date=meta.release_date,
            isrc=meta.isrc,
            track_id=track.id if track else None,
            provider=provider_name,
            provider_track_id=provider_track_id,
            quality_capabilities=caps,
            preview_available=preview_available,
            resolution_ref=f"{provider_name}:{provider_track_id}",
        )

    async def preview(
        self,
        *,
        provider: str,
        provider_track_id: str,
    ) -> PreviewResult:
        """Prefer official provider preview; do not generate illegal samples."""
        source = await self.providers.preview(provider, provider_track_id)
        if source is None:
            # Fallback: short resolve is not automatic sample generation —
            # only return if provider itself offers preview.
            return PreviewResult(source=None)

        return PreviewResult(source=source, from_cache=False)

    async def download(
        self,
        *,
        provider: str,
        provider_track_id: str,
        quality: str = "medium",
        user_id: UUID | None = None,
    ) -> DownloadResult:
        """
        Authorization/entitlement should be checked by the API layer before calling.
        Flow: cache lookup → HIT signed URL | MISS → resolve → store (single-flight).
        """
        try:
            aq = AudioQuality(quality.lower())
        except ValueError:
            aq = AudioQuality.MEDIUM
            quality = aq.value

        cache_svc = CacheService(self.session, storage=self.storage, settings=self.settings)

        hit = await cache_svc.lookup(
            provider=provider, provider_track_id=provider_track_id, quality=aq
        )
        if hit is not None:
            signed = await cache_svc.signed_delivery(hit)
            return DownloadResult(
                signed_url=signed,
                storage_key=hit.storage_key,
                quality=quality,
                from_cache=True,
                track_id=hit.track_id,
                content_hash=hit.content_hash,
                expires_at=hit.expires_at,
            )

        source = await self.providers.resolve(provider, provider_track_id, quality=quality)
        if source is None:
            raise ProviderUnavailableError("Could not resolve audio source")

        if source.body is not None:
            entry, from_cache = await cache_svc.get_or_acquire(
                provider=provider,
                provider_track_id=provider_track_id,
                quality=aq,
                acquire_fn=lambda: _async_const(source.body),
            )
            signed = await cache_svc.signed_delivery(entry)
            return DownloadResult(
                signed_url=signed,
                storage_key=entry.storage_key,
                quality=quality,
                from_cache=from_cache,
                track_id=entry.track_id,
                content_hash=entry.content_hash,
                expires_at=entry.expires_at,
            )

        # URL-based source: acquire internally, then deliver only our signed storage URL.
        from app.services.transfer import TransferManager

        transfer = TransferManager()
        entry, from_cache = await cache_svc.get_or_acquire(
            provider=provider,
            provider_track_id=provider_track_id,
            quality=aq,
            acquire_fn=lambda: transfer.acquire(source),
        )
        signed = await cache_svc.signed_delivery(entry)
        logger.info(
            "download_transferred_and_cached",
            provider=provider,
            provider_track_id=provider_track_id,
            quality=quality,
            user_id=str(user_id) if user_id else None,
        )
        return DownloadResult(
            signed_url=signed,
            storage_key=entry.storage_key,
            quality=quality,
            from_cache=from_cache,
            track_id=entry.track_id,
            content_hash=entry.content_hash,
            expires_at=entry.expires_at,
        )


    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _ensure_provider(self, name: str) -> Provider:
        existing = await self.session.scalar(select(Provider).where(Provider.name == name))
        if existing:
            return existing
        p = Provider(name=name, enabled=True, priority=100)
        self.session.add(p)
        await self.session.flush()
        return p

    async def _upsert_track_from_metadata(
        self, db_provider: Provider, meta: TrackMetadata
    ) -> Track:
        pt = await self.session.scalar(
            select(ProviderTrack).where(
                ProviderTrack.provider_id == db_provider.id,
                ProviderTrack.provider_track_id == meta.provider_track_id,
            )
        )
        if pt and pt.track_id:
            track = await self.session.get(Track, pt.track_id)
            if track:
                pt.metadata_snapshot = {
                    "title": meta.title,
                    "artists": meta.artists,
                    "album": meta.album,
                    "isrc": meta.isrc,
                    "duration": meta.duration_seconds,
                }
                pt.last_resolved_at = datetime.now(UTC)
                await self.session.flush()
                return track

        # Create track
        slug_base = _slugify(meta.title)
        track = Track(
            title=meta.title,
            slug=f"{slug_base}-{meta.provider_track_id}"[:255],
            duration=meta.duration_seconds,
            isrc=meta.isrc,
            status=TrackStatus.PUBLISHED,
            artwork_url=meta.artwork_url,
        )
        self.session.add(track)
        await self.session.flush()

        if pt is None:
            pt = ProviderTrack(
                provider_id=db_provider.id,
                provider_track_id=meta.provider_track_id,
                track_id=track.id,
                metadata_snapshot={
                    "title": meta.title,
                    "artists": meta.artists,
                    "album": meta.album,
                    "isrc": meta.isrc,
                    "duration": meta.duration_seconds,
                },
                last_resolved_at=datetime.now(UTC),
            )
            self.session.add(pt)
        else:
            pt.track_id = track.id
            pt.last_resolved_at = datetime.now(UTC)

        await self.session.flush()
        return track

    async def _find_cache(
        self, provider: str, provider_track_id: str, quality: AudioQuality
    ) -> CacheEntry | None:
        now = datetime.now(UTC)
        result = await self.session.scalar(
            select(CacheEntry).where(
                CacheEntry.provider == provider,
                CacheEntry.provider_track_id == provider_track_id,
                CacheEntry.quality == quality,
                CacheEntry.status == CacheEntryStatus.READY,
                CacheEntry.expires_at > now,
            )
        )
        return result

    async def _touch_cache(self, entry: CacheEntry) -> None:
        entry.last_accessed_at = datetime.now(UTC)
        entry.access_count += 1
        entry.requests_24h += 1
        entry.requests_7d += 1
        await self.session.flush()

    async def _store_and_cache(
        self,
        *,
        provider: str,
        provider_track_id: str,
        quality: AudioQuality,
        body: bytes,
        source: ResolvedSource,
    ) -> DownloadResult:
        import hashlib

        content_hash = hashlib.sha256(body).hexdigest()
        storage_key = f"cache/{provider}/{provider_track_id}/{quality.value}/{content_hash[:16]}"

        await self.storage.put(
            storage_key,
            body,
            bucket=StorageBucket.CACHE,
            content_type=f"audio/{source.codec or 'mpeg'}",
        )

        ttl_hours = self.settings.cache_ttl_medium_demand_hours
        expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)

        entry = CacheEntry(
            content_hash=content_hash,
            provider=provider,
            provider_track_id=provider_track_id,
            quality=quality,
            storage_key=storage_key,
            size=len(body),
            expires_at=expires_at,
            status=CacheEntryStatus.READY,
        )
        self.session.add(entry)
        await self.session.flush()

        signed = await self.storage.signed_url(storage_key, bucket=StorageBucket.CACHE)
        return DownloadResult(
            signed_url=signed,
            storage_key=storage_key,
            quality=quality.value,
            from_cache=False,
            content_hash=content_hash,
            expires_at=expires_at,
        )

    async def download_by_track_id(
        self,
        *,
        track_id: UUID,
        quality: str = "medium",
        user_id: UUID | None = None,
    ) -> DownloadResult:
        """Catalog track download — prefers permanent artist assets / cache by track_id."""
        try:
            aq = AudioQuality(quality.lower())
        except ValueError:
            aq = AudioQuality.MEDIUM
            quality = aq.value

        track = await self.session.get(Track, track_id)
        if track is None:
            raise NotFoundError("Track not found")
        if track.status != TrackStatus.PUBLISHED:
            raise NotFoundError("Track is not published")

        cache_svc = CacheService(self.session, storage=self.storage, settings=self.settings)
        hit = await cache_svc.lookup_by_track(track_id=track_id, quality=aq)
        if hit is not None:
            signed = await cache_svc.signed_delivery(hit)
            return DownloadResult(
                signed_url=signed,
                storage_key=hit.storage_key,
                quality=quality,
                from_cache=True,
                track_id=track_id,
                content_hash=hit.content_hash,
                expires_at=hit.expires_at,
            )

        # Fallback: provider mapping
        pt = await self.session.scalar(
            select(ProviderTrack).where(ProviderTrack.track_id == track_id).limit(1)
        )
        if pt is not None:
            provider = await self.session.get(Provider, pt.provider_id)
            if provider:
                return await self.download(
                    provider=provider.name,
                    provider_track_id=pt.provider_track_id,
                    quality=quality,
                    user_id=user_id,
                )

        raise NotFoundError("No playable source for track")



async def _async_const(value: bytes) -> bytes:
    return value
