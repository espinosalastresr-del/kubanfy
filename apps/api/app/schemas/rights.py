from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

class CollaboratorSplitRequest(BaseModel):
    artist_id: UUID
    role: str = Field(default="artist", min_length=1, max_length=32)
    share_bps: int = Field(gt=0, le=10000)

class CollaboratorSplitsRequest(BaseModel):
    scope_type: str
    scope_id: UUID
    splits: list[CollaboratorSplitRequest]

class CollaboratorSplitResponse(BaseModel):
    id: UUID
    artist_id: UUID
    role: str
    share_bps: int
    generation: int
    active: bool
    created_at: datetime
    model_config={"from_attributes":True}

class RoyaltyLedgerRequest(BaseModel):
    amount_cents: int = Field(ge=0)
    source_type: str = Field(min_length=1, max_length=32)
    idempotency_key: str = Field(min_length=1, max_length=160)
    direction: str = "credit"
    source_id: UUID | None = None
    currency: str = "CUP"
    metadata: dict = Field(default_factory=dict)

class RoyaltyLedgerResponse(BaseModel):
    id: UUID
    account_id: UUID
    amount_cents: int
    currency: str
    direction: str
    source_type: str
    idempotency_key: str
    created_at: datetime
    model_config={"from_attributes":True}


class RoyaltySettlementRequest(BaseModel):
    period_start: datetime
    period_end: datetime
    gross_cents: int = Field(ge=0)
    net_cents: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=160)
    currency: str = "CUP"


class RoyaltySettlementResponse(BaseModel):
    id: UUID
    account_id: UUID
    period_start: datetime
    period_end: datetime
    gross_cents: int
    net_cents: int
    currency: str
    status: str
    idempotency_key: str
    created_at: datetime
    model_config = {"from_attributes": True}
