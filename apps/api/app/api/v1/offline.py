"""Offline/bootstrap API endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from app.core.config import get_settings
from app.core.exceptions import ProviderUnavailableError

from app.api.deps import CurrentUser, DbSession
from app.core.logging import get_logger
from app.schemas.offline import OfflineLicenseResponse, OfflineLicenseValidateRequest
from app.services.offline_license import OfflineLicenseService

logger = get_logger(__name__)

router = APIRouter(prefix="/offline", tags=["offline"])


def resolve_offline_license_public_key(
    *, algorithm: str, public_key: str, private_key: str
) -> str:
    """Return the configured public key, deriving it from the private key if omitted."""
    if algorithm != "RS256":
        raise ProviderUnavailableError("Offline license verification is not configured")
    if public_key.strip():
        return public_key.replace("\\n", "\n").strip() + "\n"
    if not private_key.strip():
        raise ProviderUnavailableError("Offline license verification is not configured")
    try:
        private = serialization.load_pem_private_key(
            private_key.replace("\\n", "\n").encode("utf-8"),
            password=None,
        )
    except (TypeError, ValueError) as exc:
        raise ProviderUnavailableError("Offline license verification is not configured") from exc
    if not isinstance(private, rsa.RSAPrivateKey):
        raise ProviderUnavailableError("Offline license verification is not configured")
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


@router.get("/licenses/public-key")
async def offline_license_public_key() -> dict[str, str]:
    """Expose only the RS256 verification key required by offline clients."""
    settings = get_settings()
    return {
        "algorithm": "RS256",
        "public_key": resolve_offline_license_public_key(
            algorithm=settings.offline_license_algorithm,
            public_key=settings.offline_license_public_key,
            private_key=settings.offline_license_private_key,
        ),
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
