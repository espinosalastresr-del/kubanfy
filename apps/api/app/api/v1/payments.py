"""Payment endpoints — user create/submit; admin approve/reject via permissions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models.user import User
from app.schemas.payments import (
    PaymentCreateRequest,
    PaymentOrderResponse,
    PaymentRejectRequest,
    PaymentSubmitRequest,
)
from app.services.payment import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", response_model=PaymentOrderResponse, status_code=201)
async def create_payment(
    body: PaymentCreateRequest,
    user: CurrentUser,
    session: DbSession,
) -> PaymentOrderResponse:
    order = await PaymentService(session).create_order(
        user.id,
        amount_cents=body.amount_cents,
        currency=body.currency,
        method=body.method,
        plan_code=body.plan_code,
        reference=body.reference,
        idempotency_key=body.idempotency_key,
    )
    return PaymentOrderResponse.model_validate(order)


@router.get("", response_model=list[PaymentOrderResponse])
async def list_my_payments(user: CurrentUser, session: DbSession) -> list[PaymentOrderResponse]:
    orders = await PaymentService(session).list_for_user(user.id)
    return [PaymentOrderResponse.model_validate(o) for o in orders]


@router.post("/{order_id}/submit", response_model=PaymentOrderResponse)
async def submit_payment(
    order_id: UUID,
    body: PaymentSubmitRequest,
    user: CurrentUser,
    session: DbSession,
) -> PaymentOrderResponse:
    order = await PaymentService(session).submit_for_review(
        order_id, user.id, proof_storage_key=body.proof_storage_key
    )
    return PaymentOrderResponse.model_validate(order)


@router.get("/admin/pending", response_model=list[PaymentOrderResponse])
async def admin_pending(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("payments.read"))],
) -> list[PaymentOrderResponse]:
    orders = await PaymentService(session).list_pending_review()
    return [PaymentOrderResponse.model_validate(o) for o in orders]


@router.post("/admin/{order_id}/approve", response_model=PaymentOrderResponse)
async def admin_approve(
    order_id: UUID,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("payments.verify"))],
) -> PaymentOrderResponse:
    order = await PaymentService(session).approve(order_id, user.id)
    return PaymentOrderResponse.model_validate(order)


@router.post("/admin/{order_id}/reject", response_model=PaymentOrderResponse)
async def admin_reject(
    order_id: UUID,
    body: PaymentRejectRequest,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("payments.verify"))],
) -> PaymentOrderResponse:
    order = await PaymentService(session).reject(order_id, user.id, reason=body.reason)
    return PaymentOrderResponse.model_validate(order)
