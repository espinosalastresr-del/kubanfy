"""Mock music provider for development and contract tests.

Simulates success, 404, 429, 500, timeout, expired source, malformed metadata
via special provider_track_id prefixes / query keywords.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.core.exceptions import (
    NotFoundError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    SourceExpiredError,
)
from app.providers.base import (
    AuthType,
    MusicProvider,
    ProviderCapabilities,
    ProviderHealth,
    ProviderHealthStatus,
    ResolvedSource,
    SourceType,
    TrackMetadata,
)

# Deterministic catalog for tests
_CATALOG: dict[str, TrackMetadata] = {
    "mock-1": TrackMetadata(
        provider_track_id="mock-1",
        title="Guantanamera",
        artists=["Compay Segundo"],
        album="Buena Vista Social Club",
        duration_seconds=252.0,
        isrc="QZMOCK000001",
        artwork_url="https://example.com/art/mock-1.jpg",
    ),
    "mock-2": TrackMetadata(
        provider_track_id="mock-2",
        title="Chan Chan",
        artists=["Buena Vista Social Club"],
        album="Buena Vista Social Club",
        duration_seconds=257.0,
        isrc="QZMOCK000002",
        artwork_url="https://example.com/art/mock-2.jpg",
    ),
    "mock-3": TrackMetadata(
        provider_track_id="mock-3",
        title="Dos Gardenias",
        artists=["Ibrahim Ferrer"],
        album="Buena Vista Social Club",
        duration_seconds=201.0,
        isrc="QZMOCK000003",
    ),
}


class MockProvider(MusicProvider):
    name = "mock"
    priority = 10  # high priority for dev

    def __init__(self, *, fail_health: bool = False) -> None:
        self._fail_health = fail_health
        self._call_counts: dict[str, int] = {}

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            metadata=True,
            search=True,
            preview=True,
            audio=True,
            lossless=True,
            supports_range=True,
            supports_signed_urls=True,
            auth_type=AuthType.NONE,
            max_bit_depth=16,
            max_sample_rate=44100,
        )

    def is_available(self) -> bool:
        return True

    async def health_check(self) -> ProviderHealth:
        if self._fail_health:
            return ProviderHealth(
                status=ProviderHealthStatus.OFFLINE,
                message="Mock forced offline",
            )
        return ProviderHealth(
            status=ProviderHealthStatus.HEALTHY,
            message="Mock provider OK",
            metadata_success_rate=1.0,
            resolve_success_rate=1.0,
            average_latency_ms=5.0,
            last_success=datetime.now(UTC),
        )

    async def search(self, query: str, *, limit: int = 20) -> list[TrackMetadata]:
        self._bump("search")
        q = query.lower().strip()
        if q in ("__error__", "__500__"):
            raise ProviderUnavailableError("Mock search failure")
        if q == "__429__":
            raise ProviderRateLimitedError("Mock rate limit")
        if q == "__timeout__":
            await asyncio.sleep(30)
            return []

        results = [
            t
            for t in _CATALOG.values()
            if q in t.title.lower() or any(q in a.lower() for a in t.artists)
        ]
        if not q:
            results = list(_CATALOG.values())
        return results[:limit]

    async def get_track(self, provider_track_id: str) -> TrackMetadata | None:
        self._bump("get_track")
        if provider_track_id == "mock-not-found":
            return None
        if provider_track_id == "mock-malformed":
            return TrackMetadata(
                provider_track_id="mock-malformed",
                title="",  # malformed: empty title
                artists=[],
            )
        return _CATALOG.get(provider_track_id)

    async def resolve(
        self,
        provider_track_id: str,
        *,
        quality: str = "medium",
    ) -> ResolvedSource | None:
        self._bump("resolve")
        if provider_track_id == "mock-not-found":
            raise NotFoundError("Track not found on mock provider")
        if provider_track_id == "mock-429":
            raise ProviderRateLimitedError("Mock rate limit on resolve")
        if provider_track_id == "mock-500":
            raise ProviderUnavailableError("Mock server error")
        if provider_track_id == "mock-expired":
            raise SourceExpiredError("Mock source expired")
        if provider_track_id == "mock-timeout":
            await asyncio.sleep(30)
            return None
        if provider_track_id not in _CATALOG and not provider_track_id.startswith("mock-"):
            return None

        meta = _CATALOG.get(provider_track_id)
        duration = meta.duration_seconds if meta else 180.0
        bitrate = {"low": 128, "medium": 256, "lossless": 1411}.get(quality, 256)

        return ResolvedSource(
            source_type=SourceType.SIGNED_URL,
            url=f"https://mock.kubanfy.local/audio/{provider_track_id}/{quality}.bin?sig=test",
            expiry=datetime.now(UTC) + timedelta(hours=1),
            codec="flac" if quality == "lossless" else "aac",
            bit_depth=16 if quality == "lossless" else None,
            sample_rate=44100,
            channels=2,
            bitrate_kbps=bitrate,
            duration_seconds=duration,
            size_bytes=int((bitrate * 1000 / 8) * (duration or 180)),
            supports_range=True,
            headers={"X-Mock-Provider": "true"},
        )

    async def preview(self, provider_track_id: str) -> ResolvedSource | None:
        self._bump("preview")
        if provider_track_id not in _CATALOG:
            return None
        return ResolvedSource(
            source_type=SourceType.SIGNED_URL,
            url=f"https://mock.kubanfy.local/preview/{provider_track_id}.mp3?sig=test",
            expiry=datetime.now(UTC) + timedelta(minutes=30),
            codec="mp3",
            bitrate_kbps=96,
            duration_seconds=30.0,
            supports_range=False,
        )

    def _bump(self, op: str) -> None:
        self._call_counts[op] = self._call_counts.get(op, 0) + 1
