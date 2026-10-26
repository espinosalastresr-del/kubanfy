"""Public entitlement response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EntitlementResponse(BaseModel):
    id: UUID
    scope_type: str
    scope_id: UUID | None
    source: str
    status: str
    starts_at: datetime
    expires_at: datetime | None
    created_at: datetime
    plan_code: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
