"""Artist portal and public catalog schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ArtistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    bio: str | None = None
    country: str = Field(default="CU", min_length=2, max_length=2)


class ArtistUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    bio: str | None = None
    country: str = Field(min_length=2, max_length=2)


class ArtistResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    bio: str | None
    country: str
    status: str
    verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicTrackResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    duration: float | None
    explicit: bool
    language: str | None
    release_id: UUID | None
    release_title: str | None


class PublicReleaseResponse(BaseModel):
    id: UUID
    title: str
    type: str
    artwork_asset: str | None
    release_date: datetime | None
    status: str


class TrackUploadResponse(BaseModel):
    track_id: UUID
    status: str
    master_storage_key: str
    content_hash: str
    duration: float | None
    job_id: UUID | None = None


class PublishTrackResponse(BaseModel):
    track_id: UUID
    status: str
