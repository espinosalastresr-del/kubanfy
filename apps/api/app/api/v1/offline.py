"""Offline/bootstrap API endpoints."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, Response

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.offline import OfflineLicenseResponse, OfflineLicenseValidateRequest
from app.services.offline_license import OfflineLicenseService

logger = get_logger(__name__)

router = APIRouter(prefix="/offline", tags=["offline"])


@router.get("/licenses/public-key")
async def offline_license_public_key(response: Response) -> dict[str, str]:
    """Expose only the RS256 verification key required by offline clients."""
    public_key = get_settings().offline_license_public_key
    if not public_key:
        raise HTTPException(status_code=503, detail="Offline license verification is unavailable")
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
    return {
        "algorithm": "RS256",
        "key_id": hashlib.sha256(public_key.encode("utf-8")).hexdigest()[:16],
        "public_key": public_key,
    }


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
