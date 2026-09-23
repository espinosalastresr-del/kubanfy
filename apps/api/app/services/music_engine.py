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
    AudioAsset,
    AudioQuality,
    CacheEntry,
    CacheEntryStatus,
    Provider,
    ProviderTrack,
    SourceType,
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
    resolution_ref: str | None = None


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
    storage_bucket: StorageBucket = StorageBucket.CACHE


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
        """Resolve external metadata without promoting it into the owned catalog."""
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

        db_provider = await self._ensure_provider(provider_name)

        # ProviderTrack is only a durable external reference. A Track is created
        # exclusively by the artist catalog/upload workflow.
        track = await self._ensure_provider_track(db_provider, meta)

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
            preview_available=bool(p and p.capabilities.preview),
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
        """Resolve, acquire, cache and return only our signed storage URL."""
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

    async def _ensure_provider(self, name: str) -> Provider:
        existing = await self.session.scalar(select(Provider).where(Provider.name == name))
        if existing:
            return existing
        p = Provider(name=name, enabled=True, priority=100)
        self.session.add(p)
        await self.session.flush()
        return p

    async def _ensure_provider_track(
        self, db_provider: Provider, meta: TrackMetadata
    ) -> Track | None:
        """Persist provider metadata without creating a first-party Track.

        A ProviderTrack may point at a first-party Track later, after an artist
        uploads/claims the corresponding content and the rights workflow accepts it.
        """
        pt = await self.session.scalar(
            select(ProviderTrack).where(
                ProviderTrack.provider_id == db_provider.id,
                ProviderTrack.provider_track_id == meta.provider_track_id,
            )
        )
        snapshot: dict[str, Any] = {
            "title": meta.title,
            "artists": meta.artists,
            "album": meta.album,
            "isrc": meta.isrc,
            "duration": meta.duration_seconds,
            "artwork_url": meta.artwork_url,
            "release_date": meta.release_date,
        }

        if pt is None:
            pt = ProviderTrack(
                provider_id=db_provider.id,
                provider_track_id=meta.provider_track_id,
                metadata_snapshot=snapshot,
                last_resolved_at=datetime.now(UTC),
            )
            self.session.add(pt)
        else:
            pt.metadata_snapshot = snapshot
            pt.last_resolved_at = datetime.now(UTC)

        await self.session.flush()

        if pt.track_id is None:
            return None
        return await self.session.get(Track, pt.track_id)

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
        """Catalog track download — only for first-party published tracks."""
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

        # First-party catalog playback must use its owned permanent asset.
        # ProviderTrack is metadata/reference only and must never replace it.
        asset = await self.session.scalar(
            select(AudioAsset)
            .where(
                AudioAsset.track_id == track_id,
                AudioAsset.quality == aq,
                AudioAsset.is_active.is_(True),
            )
            .order_by(AudioAsset.created_at.desc())
            .limit(1)
        )
        if asset is None:
            raise NotFoundError(f"No published {aq.value} audio asset available for track")
        if asset.source_type not in (SourceType.ARTIST_UPLOAD, SourceType.DERIVATIVE):
            raise NotFoundError("Track has no first-party playable asset")
        if not asset.content_hash or not asset.storage_key:
            raise NotFoundError("Track asset is incomplete")

        signed = await self.storage.signed_url(
            asset.storage_key,
            bucket=StorageBucket.PERMANENT,
        )
        return DownloadResult(
            signed_url=signed,
            storage_key=asset.storage_key,
            quality=quality,
            from_cache=False,
            track_id=track_id,
            content_hash=asset.content_hash,
            storage_bucket=StorageBucket.PERMANENT,
        )


async def _async_const(value: bytes) -> bytes:
    return value
