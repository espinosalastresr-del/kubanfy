"""User entitlement API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.entitlement import EntitlementResponse
from app.services.entitlement import EntitlementService

router = APIRouter(prefix="/entitlements", tags=["entitlements"])


@router.get("/me", response_model=list[EntitlementResponse])
async def my_entitlements(
    user: CurrentUser,
    session: DbSession,
) -> list[EntitlementResponse]:
    entitlements = await EntitlementService(session).list_active(user.id)
    return [EntitlementResponse.model_validate(item) for item in entitlements]
