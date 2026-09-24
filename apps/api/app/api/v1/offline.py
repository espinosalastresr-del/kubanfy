from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.offline import OfflineLicenseResponse, OfflineLicenseValidateRequest
from app.services.offline_license import OfflineLicenseService

router = APIRouter(prefix="/offline", tags=["offline"])


@router.post("/licenses/validate", response_model=OfflineLicenseResponse)
async def validate_offline_license(
    body: OfflineLicenseValidateRequest,
    session: DbSession,
    user: CurrentUser,
) -> OfflineLicenseResponse:
    row = await OfflineLicenseService(session).validate(
        user_id=user.id,
        token=body.token,
        device_id=body.device_id,
    )
    return OfflineLicenseResponse(
        license_id=row.id,
        track_id=row.track_id,
        device_id=body.device_id,
        quality=row.quality,
        content_hash=row.content_hash,
        asset_version=row.asset_version,
        expires_at=row.expires_at.isoformat(),
    )
