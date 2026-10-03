"""Offline/bootstrap API endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core.logging import get_logger
from app.schemas.offline import OfflineLicenseResponse, OfflineLicenseValidateRequest
from app.services.offline_license import OfflineLicenseService

logger = get_logger(__name__)

router = APIRouter(prefix="/offline", tags=["offline"])


@router.post("/licenses/validate", response_model=OfflineLicenseResponse)
async def validate_offline_license(
    body: OfflineLicenseValidateRequest,
    session: DbSession,
    user: CurrentUser,
) -> OfflineLicenseResponse:
    logger.info(
        "offline_license_validation_started",
        category="offline.license.validate",
        user_id=str(user.id),
        track_id=str(body.track_id) if getattr(body, "track_id", None) else None,
        device_id_present=bool(body.device_id),
    )
    row = await OfflineLicenseService(session).validate(
        user_id=user.id,
        token=body.token,
        device_id=body.device_id,
    )
    logger.info(
        "offline_license_validation_succeeded",
        category="offline.license.validate",
        user_id=str(user.id),
        track_id=str(row.track_id),
        license_id=str(row.id),
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
