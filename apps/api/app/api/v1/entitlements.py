"""User entitlement API."""
from __future__ import annotations
from fastapi import APIRouter
from app.api.deps import CurrentUser, DbSession
from app.schemas.entitlement import EntitlementResponse
from app.services.entitlement import EntitlementService

router = APIRouter(prefix="/entitlements", tags=["entitlements"])

@router.get("/me", response_model=list[EntitlementResponse])
async def my_entitlements(user: CurrentUser, session: DbSession) -> list[EntitlementResponse]:
    entitlements = await EntitlementService(session).list_active(user.id)
    response = []
    for item in entitlements:
        metadata = item.metadata_json or {}
        features = {key: metadata[key] for key in ("downloads", "quality_max", "seats") if key in metadata}
        response.append(EntitlementResponse(
            id=item.id, scope_type=item.scope_type.value, scope_id=item.scope_id,
            source=item.source.value, status=item.status.value, starts_at=item.starts_at,
            expires_at=item.expires_at, created_at=item.created_at,
            plan_code=metadata.get("plan_code"), features=features,
        ))
    return response
