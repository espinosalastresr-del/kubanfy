"""Music API request/response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class MusicUpdateRequest(BaseModel):
    provider: str | None = Field(default=None, max_length=64)
    provider_track_id: str | None = Field(default=None, max_length=255)
    query: str | None = Field(default=None, max_length=500)


class MusicUpdateResponse(BaseModel):
    title: str
    artists: list[str]
    album: str | None = None
    duration: float | None = None
    artwork: str | None = None
    release_date: str | None = None
    isrc: str | None = None
    track_id: UUID | None = None
    provider: str
    provider_track_id: str
    quality_capabilities: list[str] = []
    preview_available: bool = False
    resolution_ref: str | None = None


class MusicPreviewRequest(BaseModel):
    provider: str | None = Field(default=None, max_length=64)
    provider_track_id: str | None = Field(default=None, max_length=255)
    track_id: UUID | None = None


class MusicPreviewResponse(BaseModel):
    available: bool
    url: str | None = None
    expires_in_seconds: int | None = None
    duration_seconds: float | None = None
    codec: str | None = None


class MusicDownloadRequest(BaseModel):
    provider: str | None = Field(default=None, max_length=64)
    provider_track_id: str | None = Field(default=None, max_length=255)
    track_id: UUID | None = None
    quality: str = Field(default="medium", pattern="^(low|medium|lossless)$")
    device_id: str | None = Field(default=None, max_length=128)


class MusicPlaybackResponse(BaseModel):
    url: str
    expires_in_seconds: int
    quality: str
    track_id: UUID
    content_hash: str | None = None
    kby_key: str


class MusicDownloadResponse(BaseModel):
    url: str | None = None
    expires_in_seconds: int | None = None
    quality: str
    from_cache: bool
    track_id: UUID | None = None
    storage_key: str | None = None
    content_hash: str | None = None
    kby_key: str | None = None
    size_bytes: int | None = None
    download_ticket: str | None = None
    offline_license: str | None = None
    offline_license_expires_at: str | None = None


class TrackSearchResult(BaseModel):
    provider: str
    provider_track_id: str
    title: str
    artists: list[str]
    album: str | None = None
    duration: float | None = None
    artwork: str | None = None
    isrc: str | None = None
