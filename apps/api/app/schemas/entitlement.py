"""Entitlement API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EntitlementResponse(BaseModel):
    id: UUID
    scope_type: str
    scope_id: UUID | None
    source: str
    status: str
    starts_at: datetime
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
