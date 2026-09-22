"""Payment API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentCreateRequest(BaseModel):
    amount_cents: int = Field(gt=0)
    currency: str = Field(default="CUP", min_length=3, max_length=3)
    method: str = Field(default="bank_transfer", pattern="^(bank_transfer|cash)$")
    plan_code: str | None = Field(default="premium", max_length=32)
    reference: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=128)


class PaymentSubmitRequest(BaseModel):
    proof_storage_key: str | None = Field(default=None, max_length=512)


class PaymentRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class PaymentOrderResponse(BaseModel):
    id: UUID
    amount_cents: int
    currency: str
    method: str
    status: str
    plan_code: str | None
    reference: str | None
    created_at: datetime
    verified_at: datetime | None = None
    rejection_reason: str | None = None

    model_config = {"from_attributes": True}
