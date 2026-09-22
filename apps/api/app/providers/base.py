"""Music provider interface.

MusicEngine never talks to a concrete provider — only via ProviderManager.
Providers resolve a source; they do not necessarily download audio.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ProviderCapability(StrEnum):
    METADATA = "metadata"
    SEARCH = "search"
    PREVIEW = "preview"
    AUDIO = "audio"
    LOSSLESS = "lossless"
    HI_RES = "hi_res"
    SUPPORTS_RANGE = "supports_range"
    SUPPORTS_SIGNED_URLS = "supports_signed_urls"


class AuthType(StrEnum):
    NONE = "none"
    SERVER_CREDENTIAL = "server_credential"
    USER_CREDENTIAL = "user_credential"
    SUBSCRIPTION = "subscription"


class ProviderHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"
    OFFLINE = "offline"
    NOT_FOUND = "not_found"
    COOLDOWN = "cooldown"
    UNAVAILABLE = "unavailable"  # missing credentials


class SourceType(StrEnum):
    SIGNED_URL = "signed_url"
    STREAM = "stream"
    MANIFEST = "manifest"
    OBJECT_REF = "object_ref"
    BODY = "body"


@dataclass
class ProviderCapabilities:
    metadata: bool = True
    search: bool = True
    preview: bool = False
    audio: bool = False
    lossless: bool = False
    hi_res: bool = False
    max_bit_depth: int | None = None
    max_sample_rate: int | None = None
    requires_user_auth: bool = False
    requires_server_auth: bool = False
    supports_range: bool = False
    supports_signed_urls: bool = False
    auth_type: AuthType = AuthType.NONE

    def has(self, cap: ProviderCapability) -> bool:
        return bool(getattr(self, cap.value, False))


@dataclass
class TrackMetadata:
    provider_track_id: str
    title: str
    artists: list[str] = field(default_factory=list)
    album: str | None = None
    duration_seconds: float | None = None
    artwork_url: str | None = None
    release_date: str | None = None
    isrc: str | None = None
    explicit: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedSource:
    """Temporary resolved audio source. Never store signed URLs as permanent truth."""

    source_type: SourceType
    url: str | None = None
    expiry: datetime | None = None
    codec: str | None = None
    bit_depth: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    bitrate_kbps: int | None = None
    duration_seconds: float | None = None
    size_bytes: int | None = None
    supports_range: bool = False
    body: bytes | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class ProviderHealth:
    status: ProviderHealthStatus
    message: str | None = None
    metadata_success_rate: float | None = None
    resolve_success_rate: float | None = None
    average_latency_ms: float | None = None
    last_success: datetime | None = None
    last_failure: datetime | None = None


class MusicProvider(ABC):
    """Base adapter for external music sources."""

    name: str = "base"
    priority: int = 100  # lower = preferred

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        ...

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        ...

    @abstractmethod
    async def search(self, query: str, *, limit: int = 20) -> list[TrackMetadata]:
        ...

    @abstractmethod
    async def get_track(self, provider_track_id: str) -> TrackMetadata | None:
        ...

    @abstractmethod
    async def resolve(
        self,
        provider_track_id: str,
        *,
        quality: str = "medium",
    ) -> ResolvedSource | None:
        """Resolve a playable/downloadable source. May return None if unavailable."""
        ...

    async def preview(self, provider_track_id: str) -> ResolvedSource | None:
        """Official preview if available. Default: None."""
        return None

    def is_available(self) -> bool:
        """True if credentials/config allow this provider to run."""
        return True
