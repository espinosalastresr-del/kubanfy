"""Artist release and track management schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.music import ReleaseType, TrackStatus


class ReleaseCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    type: ReleaseType = ReleaseType.SINGLE
    description: str | None = None
    artwork_asset: str | None = Field(default=None, max_length=512)
    release_date: datetime | None = None


class ReleaseUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    type: ReleaseType
    description: str | None = None
    artwork_asset: str | None = Field(default=None, max_length=512)
    release_date: datetime | None = None


class ReleaseScheduleRequest(BaseModel):
    publish_at: datetime | None = None
    unpublish_at: datetime | None = None


class ReleaseResponse(BaseModel):
    id: UUID
    artist_id: UUID
    title: str
    type: str
    artwork_asset: str | None
    release_date: datetime | None
    status: str
    description: str | None
    scheduled_publish_at: datetime | None = None
    scheduled_unpublish_at: datetime | None = None

    model_config = {"from_attributes": True}


class TrackUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    isrc: str | None = Field(default=None, max_length=16)
    explicit: bool = False
    language: str | None = Field(default=None, max_length=10)
    release_date: datetime | None = None
    artwork_url: str | None = Field(default=None, max_length=512)
    release_id: UUID | None = None


class TrackStatusResponse(BaseModel):
    track_id: UUID
    status: TrackStatus
