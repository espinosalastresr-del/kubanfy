from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class OfflineLicenseValidateRequest(BaseModel):
    token: str = Field(min_length=32, max_length=4096)
    device_id: str = Field(min_length=1, max_length=128)


class OfflineLicenseResponse(BaseModel):
    license_id: UUID
    track_id: UUID
    device_id: str
    quality: str
    content_hash: str
    asset_version: int
    expires_at: str
