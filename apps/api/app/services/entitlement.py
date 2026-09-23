"""Entitlement grants and checks.

Artist content is free by default (architecture supports future paid scopes).
Payments never mutate entitlements except via this service.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntitlementRequiredError, NotFoundError
from app.core.logging import get_logger
from app.models.entitlement import (
    Entitlement,
    EntitlementScope,
    EntitlementSource,
    EntitlementStatus,
    Plan,
    PlanCode,
)
from app.models.music import AudioAsset, SourceType

logger = get_logger(__name__)


class EntitlementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def grant(
        self,
        user_id: UUID,
        scope_type: EntitlementScope,
        *,
        scope_id: UUID | None = None,
        source: EntitlementSource = EntitlementSource.MANUAL,
        expires_at: datetime | None = None,
        metadata: dict | None = None,
        payment_order_id: UUID | None = None,
    ) -> Entitlement:
        ent = Entitlement(
            user_id=user_id,
            scope_type=scope_type,
            scope_id=scope_id,
            source=source,
            status=EntitlementStatus.ACTIVE,
            expires_at=expires_at,
            metadata_json=metadata or {},
            payment_order_id=payment_order_id,
        )
        self.session.add(ent)
        await self.session.flush()
        logger.info(
            "entitlement_granted",
            user_id=str(user_id),
            scope=scope_type.value,
            source=source.value,
        )
        return ent

    async def grant_payment_entitlement(
        self,
        *,
        user_id: UUID,
        payment_order_id: UUID,
        scope_type: EntitlementScope,
        source: EntitlementSource,
        expires_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> Entitlement:
        """Grant an entitlement once for a payment order."""
        payment_ref = str(payment_order_id)
        existing = await self.session.scalar(
            select(Entitlement).where(
                Entitlement.user_id == user_id,
                Entitlement.scope_type == scope_type,
                Entitlement.payment_order_id == payment_order_id,
            )
        )
        if existing is not None:
            return existing
        payload = dict(metadata or {})
        payload["payment_order_id"] = payment_ref
        return await self.grant(
            user_id,
            scope_type,
            source=source,
            expires_at=expires_at,
            metadata=payload,
            payment_order_id=payment_order_id,
        )

    async def revoke(self, entitlement_id: UUID) -> Entitlement:
        ent = await self.session.get(Entitlement, entitlement_id)
        if ent is None:
            raise NotFoundError("Entitlement not found")
        ent.status = EntitlementStatus.REVOKED
        await self.session.flush()
        logger.info("entitlement_revoked", entitlement_id=str(entitlement_id))
        return ent

    async def list_active(self, user_id: UUID) -> list[Entitlement]:
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(Entitlement).where(
                Entitlement.user_id == user_id,
                Entitlement.status == EntitlementStatus.ACTIVE,
            )
        )
        active: list[Entitlement] = []
        for ent in result.scalars().all():
            if ent.expires_at and ent.expires_at.replace(tzinfo=UTC) <= now:
                ent.status = EntitlementStatus.EXPIRED
                continue
            active.append(ent)
        await self.session.flush()
        return active

    async def has_premium(self, user_id: UUID) -> bool:
        for ent in await self.list_active(user_id):
            if ent.scope_type == EntitlementScope.USER_PREMIUM:
                return True
        return False

    async def can_access_track(self, user_id: UUID | None, track_id: UUID) -> bool:
        """
        Access rules (initial):
        - Artist-uploaded content: free (streaming allowed via rights, checked elsewhere)
        - Provider content: free for now; premium gate reserved for future
        - Explicit TRACK/RELEASE/ARTIST entitlements always grant access
        """
        # Specific track entitlement
        if user_id:
            for ent in await self.list_active(user_id):
                if ent.scope_type == EntitlementScope.TRACK and ent.scope_id == track_id:
                    return True
                if ent.scope_type == EntitlementScope.USER_PREMIUM:
                    return True

        # Artist uploads are free by product decision
        asset = await self.session.scalar(
            select(AudioAsset).where(
                AudioAsset.track_id == track_id,
                AudioAsset.source_type == SourceType.ARTIST_UPLOAD,
            )
        )
        if asset is not None:
            return True

        # Default: allow (platform starts free). Tighten when monetization ships.
        return True

    async def require_track_access(self, user_id: UUID | None, track_id: UUID) -> None:
        if not await self.can_access_track(user_id, track_id):
            raise EntitlementRequiredError("Entitlement required for this track")

    async def require_download_access(self, user_id: UUID) -> None:
        """Persistent/download delivery is a premium entitlement, not free streaming."""
        if not await self.has_premium(user_id):
            raise EntitlementRequiredError("Premium entitlement required for downloads")

    async def require_quality_access(self, user_id: UUID, quality: str) -> None:
        """Enforce the plan's maximum streaming/download quality."""
        order = {"low": 0, "medium": 1, "lossless": 2}
        requested = quality.lower()
        if requested not in order:
            raise EntitlementRequiredError("Unsupported audio quality")

        max_quality = "low"
        for ent in await self.list_active(user_id):
            if ent.scope_type != EntitlementScope.USER_PREMIUM:
                continue
            plan_code = (ent.metadata_json or {}).get("plan_code")
            if plan_code in {PlanCode.PREMIUM.value, PlanCode.FAMILY.value, PlanCode.STUDENT.value}:
                max_quality = "lossless"
                break
            max_quality = "medium"

        if order[requested] > order[max_quality]:
            raise EntitlementRequiredError(
                f"Audio quality {requested} requires a higher entitlement"
            )

    async def ensure_default_plans(self) -> None:
        """Idempotent seed of FREE/PREMIUM/FAMILY/STUDENT plans (no prices hardcoded as product truth)."""
        defaults = [
            (PlanCode.FREE.value, "Free", {"downloads": False, "quality_max": "medium"}),
            (PlanCode.PREMIUM.value, "Premium", {"downloads": True, "quality_max": "lossless"}),
            (
                PlanCode.FAMILY.value,
                "Family",
                {"downloads": True, "quality_max": "lossless", "seats": 6},
            ),
            (PlanCode.STUDENT.value, "Student", {"downloads": True, "quality_max": "lossless"}),
        ]
        for code, name, features in defaults:
            existing = await self.session.scalar(select(Plan).where(Plan.code == code))
            if existing is None:
                self.session.add(Plan(code=code, name=name, features=features, is_active=True))
        await self.session.flush()
