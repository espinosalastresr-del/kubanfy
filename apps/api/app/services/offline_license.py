"""Device-bound offline authorization service."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthError, NotFoundError, ValidationError
from app.core.security import create_offline_license_token, decode_offline_license_token
from app.models.device import Device, DeviceStatus
from app.models.music import AudioAsset, AudioQuality, SourceType, Track
from app.models.offline import OfflineLicense
from app.services.entitlement import EntitlementService


class OfflineLicenseService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def issue(
        self,
        *,
        user_id: UUID,
        device_id: str,
        track_id: UUID,
        quality: str,
    ) -> tuple[OfflineLicense, str]:
        if quality not in {q.value for q in AudioQuality}:
            raise ValidationError("Unsupported audio quality")

        device = await self.session.scalar(
            select(Device).where(
                Device.user_id == user_id,
                Device.device_id == device_id,
                Device.status == DeviceStatus.ACTIVE,
            )
        )
        if device is None:
            raise AuthError("Registered active device required")

        track = await self.session.scalar(select(Track).where(Track.id == track_id))
        if track is None or track.status.value != "published":
            raise NotFoundError("Track not available")

        entitlement = EntitlementService(self.session)
        await entitlement.require_download_access(user_id)
        await entitlement.require_track_access(user_id, track_id)
        await entitlement.require_quality_access(user_id, quality)

        asset = await self.session.scalar(
            select(AudioAsset)
            .where(
                AudioAsset.track_id == track_id,
                AudioAsset.quality == quality,
                AudioAsset.is_active.is_(True),
                AudioAsset.source_type.in_([SourceType.ARTIST_UPLOAD, SourceType.DERIVATIVE]),
                AudioAsset.storage_key.is_not(None),
                AudioAsset.content_hash.is_not(None),
            )
            .order_by(AudioAsset.version.desc())
        )
        if asset is None or not asset.content_hash or not asset.storage_key:
            raise NotFoundError("Offline audio asset not available")

        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=self.settings.offline_license_expire_hours)
        license_row = OfflineLicense(
            user_id=user_id,
            device_id=device.id,
            track_id=track_id,
            asset_version=asset.version,
            content_hash=asset.content_hash,
            quality=quality,
            token_hash="pending",
            expires_at=expires_at,
        )
        self.session.add(license_row)
        await self.session.flush()

        token = create_offline_license_token(
            str(user_id),
            extra_claims={
                "type": "offline_license",
                "license_id": str(license_row.id),
                "device_id": device.device_id,
                "track_id": str(track_id),
                "asset_version": asset.version,
                "quality": quality,
                "content_hash": asset.content_hash,
            },
            expires_delta=expires_at - now,
            settings=self.settings,
        )
        license_row.token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        await self.session.flush()
        return license_row, token

    async def validate(
        self,
        *,
        user_id: UUID,
        token: str,
        device_id: str,
    ) -> OfflineLicense:
        try:
            payload = decode_offline_license_token(token, self.settings)
        except ValueError as exc:
            raise AuthError("Invalid or expired offline license") from exc
        if payload.get("type") != "offline_license" or payload.get("sub") != str(user_id):
            raise AuthError("Invalid offline license")

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        row = await self.session.scalar(
            select(OfflineLicense).where(OfflineLicense.token_hash == token_hash)
        )
        if row is None or row.revoked or row.expires_at <= datetime.now(UTC):
            raise AuthError("Offline license expired or revoked")

        device = await self.session.get(Device, row.device_id)
        if (
            device is None
            or device.user_id != user_id
            or device.status != DeviceStatus.ACTIVE
            or device.device_id != device_id
        ):
            raise AuthError("Offline license device mismatch")

        if (
            payload.get("device_id") != device_id
            or payload.get("sub") != str(row.user_id)
            or payload.get("track_id") != str(row.track_id)
            or payload.get("license_id") != str(row.id)
            or payload.get("quality") != row.quality
            or payload.get("asset_version") != row.asset_version
            or payload.get("content_hash") != row.content_hash
        ):
            raise AuthError("Offline license binding mismatch")

        # A license is bound to an exact asset generation. Replacements must
        # not silently make an older offline authorization valid for the new
        # bytes, and deleted/revoked assets must stop validating as well.
        track = await self.session.scalar(select(Track).where(Track.id == row.track_id))
        if track is None or track.status.value != "published":
            raise AuthError("Offline license track is no longer published")

        asset = await self.session.scalar(
            select(AudioAsset).where(
                AudioAsset.track_id == row.track_id,
                AudioAsset.quality == row.quality,
                AudioAsset.version == row.asset_version,
                AudioAsset.is_active.is_(True),
                AudioAsset.content_hash == row.content_hash,
                AudioAsset.storage_key.is_not(None),
            )
        )
        if asset is None:
            raise AuthError("Offline license asset is no longer available")

        row.last_validated_at = datetime.now(UTC)
        row.validation_count += 1
        await self.session.flush()
        return row

    async def revoke(self, *, user_id: UUID, license_id: UUID) -> None:
        row = await self.session.get(OfflineLicense, license_id)
        if row is None or row.user_id != user_id:
            raise NotFoundError("Offline license not found")
        row.revoked = True
        row.revoked_at = datetime.now(UTC)
        await self.session.flush()
