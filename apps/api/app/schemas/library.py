"""Playlist, favorites, entitlements schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PlaylistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    visibility: str = Field(default="private", pattern="^(private|public)$")


class PlaylistRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class PlaylistResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    visibility: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlaylistTrackResponse(BaseModel):
    track_id: UUID
    position: int
    added_at: datetime

    model_config = {"from_attributes": True}


class FavoriteRequest(BaseModel):
    target_type: str = Field(pattern="^(track|artist|release)$")
    target_id: UUID


class FavoriteResponse(BaseModel):
    id: UUID
    target_type: str
    target_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class EntitlementResponse(BaseModel):
    id: UUID
    scope_type: str
    scope_id: UUID | None
    source: str
    status: str
    starts_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}
