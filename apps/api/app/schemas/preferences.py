"""User preference request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


AudioQuality = Literal["auto", "low", "medium", "high"]
Theme = Literal["system", "light", "dark"]


class UserPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audio_quality: AudioQuality | None = None
    data_saver: bool | None = None
    wifi_only_downloads: bool | None = None
    theme: Theme | None = None
    local_content_enabled: bool | None = None


class UserPreferencesResponse(BaseModel):
    id: UUID
    user_id: UUID
    audio_quality: AudioQuality
    data_saver: bool
    wifi_only_downloads: bool
    theme: Theme
    local_content_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
