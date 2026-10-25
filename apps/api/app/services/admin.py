"""Admin service: audit logging, moderation, feature flags, settings, user suspend."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.device import Session, SessionStatus
from app.models.entitlement import (
    Entitlement,
    EntitlementScope,
    EntitlementSource,
    EntitlementStatus,
    Plan,
    PlanCode,
)
from app.models.offline import OfflineLicense
from app.models.admin import (
    AuditLog,
    FeatureFlag,
    ModerationReport,
    ModerationReportType,
    ModerationStatus,
    SystemSetting,
)
from app.models.music import Track, TrackStatus
from app.models.user import User, UserStatus

logger = get_logger(__name__)

DEFAULT_FLAGS = {
    "artist_publishing": True,
    "monetization": False,
    "google_play": False,
    "maintenance_mode": False,
    "provider_youtube": False,
    "ranking": True,
    "download_system": True,
}


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def audit(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        result: str = "success",
        reason: str | None = None,
        actor_role: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        log = AuditLog(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            result=result,
            reason=reason,
            request_id=request_id,
            metadata_json=metadata or {},
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_audit_logs(self, *, limit: int = 100) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    # --- Moderation ---

    async def create_report(
        self,
        *,
        reporter_user_id: UUID | None,
        target_type: str,
        target_id: UUID,
        report_type: ModerationReportType,
        description: str | None = None,
    ) -> ModerationReport:
        report = ModerationReport(
            reporter_user_id=reporter_user_id,
            target_type=target_type,
            target_id=target_id,
            report_type=report_type,
            description=description,
            status=ModerationStatus.OPEN,
        )
        self.session.add(report)
        await self.session.flush()
        return report

    async def list_reports(
        self, *, status: ModerationStatus | None = None, limit: int = 50
    ) -> list[ModerationReport]:
        q = select(ModerationReport).order_by(ModerationReport.created_at.desc()).limit(limit)
        if status:
            q = q.where(ModerationReport.status == status)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def resolve_report(
        self,
        report_id: UUID,
        admin_id: UUID,
        *,
        status: ModerationStatus,
        notes: str | None = None,
        takedown_track: bool = False,
    ) -> ModerationReport:
        report = await self.session.get(ModerationReport, report_id)
        if report is None:
            raise NotFoundError("Report not found")
        report.status = status
        report.resolution_notes = notes
        report.resolved_at = datetime.now(UTC)
        report.assigned_to = admin_id

        if takedown_track and report.target_type == "track":
            track = await self.session.get(Track, report.target_id)
            if track:
                before = {"status": track.status.value}
                track.status = TrackStatus.TAKEDOWN
                await self.audit(
                    actor_id=admin_id,
                    action="tracks.takedown",
                    target_type="track",
                    target_id=str(track.id),
                    before=before,
                    after={"status": TrackStatus.TAKEDOWN.value},
                    reason=notes,
                )

        await self.session.flush()
        return report

    # --- User plans (manual entitlement management; no automated billing) ---

    async def list_users(
        self, *, search: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        query = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where((User.email.ilike(term)) | (User.display_name.ilike(term)))
        result = await self.session.execute(query)
        users = list(result.scalars().all())
        if not users:
            return []

        now = datetime.now(UTC)
        ent_result = await self.session.execute(
            select(Entitlement).where(
                Entitlement.user_id.in_([u.id for u in users]),
                Entitlement.scope_type == EntitlementScope.USER_PREMIUM,
                Entitlement.status == EntitlementStatus.ACTIVE,
                (Entitlement.expires_at.is_(None)) | (Entitlement.expires_at > now),
            )
        )
        plans: dict[UUID, str] = {}
        for entitlement in ent_result.scalars().all():
            code = str((entitlement.metadata_json or {}).get("plan_code") or PlanCode.PREMIUM.value)
            if entitlement.user_id not in plans or entitlement.source == EntitlementSource.MANUAL:
                plans[entitlement.user_id] = code

        return [
            {
                "id": str(u.id),
                "email": u.email,
                "display_name": u.display_name,
                "status": u.status.value,
                "email_verified": u.email_verified,
                "created_at": u.created_at.isoformat(),
                "plan_code": plans.get(u.id, PlanCode.FREE.value),
            }
            for u in users
        ]

    async def set_user_plan(
        self,
        user_id: UUID,
        admin_id: UUID,
        *,
        plan_code: PlanCode,
        expires_at: datetime | None = None,
        reason: str,
    ) -> dict[str, Any]:
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        if expires_at is not None and expires_at.tzinfo is None:
            raise ValidationError("expires_at must include a timezone")

        result = await self.session.execute(
            select(Entitlement)
            .where(
                Entitlement.user_id == user_id,
                Entitlement.scope_type == EntitlementScope.USER_PREMIUM,
                Entitlement.source == EntitlementSource.MANUAL,
                Entitlement.status == EntitlementStatus.ACTIVE,
            )
            .with_for_update()
        )
        existing = list(result.scalars().all())
        before = {
            "plan_code": (
                (existing[0].metadata_json or {}).get("plan_code", PlanCode.PREMIUM.value)
                if existing
                else PlanCode.FREE.value
            ),
            "expires_at": (
                existing[0].expires_at.isoformat()
                if existing and existing[0].expires_at
                else None
            ),
        }

        if plan_code == PlanCode.FREE:
            all_result = await self.session.execute(
                select(Entitlement)
                .where(
                    Entitlement.user_id == user_id,
                    Entitlement.scope_type == EntitlementScope.USER_PREMIUM,
                    Entitlement.status == EntitlementStatus.ACTIVE,
                )
                .with_for_update()
            )
            for entitlement in all_result.scalars().all():
                entitlement.status = EntitlementStatus.REVOKED
            effective_expiry = None
        else:
            plan = await self.session.scalar(select(Plan).where(Plan.code == plan_code.value))
            if plan is None:
                plan = Plan(
                    code=plan_code.value,
                    name=plan_code.value.title(),
                    is_active=True,
                    features={
                        "downloads": True,
                        "quality_max": "medium",
                        **({"seats": 6} if plan_code == PlanCode.FAMILY else {}),
                    },
                )
                self.session.add(plan)
                await self.session.flush()
            elif not plan.is_active:
                raise ValidationError("This plan is inactive")

            entitlement = existing[0] if existing else Entitlement(
                user_id=user_id,
                scope_type=EntitlementScope.USER_PREMIUM,
                source=EntitlementSource.MANUAL,
                status=EntitlementStatus.ACTIVE,
            )
            entitlement.user_id = user_id
            entitlement.scope_type = EntitlementScope.USER_PREMIUM
            entitlement.source = EntitlementSource.MANUAL
            entitlement.status = EntitlementStatus.ACTIVE
            entitlement.expires_at = expires_at
            entitlement.metadata_json = {
                "plan_code": plan_code.value,
                **(plan.features or {}),
                "manual_grant": True,
            }
            if not existing:
                self.session.add(entitlement)
            for duplicate in existing[1:]:
                duplicate.status = EntitlementStatus.REVOKED
            effective_expiry = expires_at.isoformat() if expires_at else None

        await self.audit(
            actor_id=admin_id,
            action="users.plan.update",
            target_type="user",
            target_id=str(user_id),
            before=before,
            after={"plan_code": plan_code.value, "expires_at": effective_expiry},
            reason=reason.strip(),
        )
        await self.session.flush()
        logger.info(
            "user_plan_updated",
            user_id=str(user_id),
            plan_code=plan_code.value,
            admin_id=str(admin_id),
        )
        return {
            "id": str(user.id),
            "email": user.email,
            "plan_code": plan_code.value,
            "expires_at": effective_expiry,
        }

    # --- Users ---

    async def suspend_user(
        self, user_id: UUID, admin_id: UUID, *, reason: str | None = None
    ) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        before = {"status": user.status.value}
        user.status = UserStatus.SUSPENDED
        now = datetime.now(UTC)
        await self.session.execute(
            update(Session)
            .where(
                Session.user_id == user_id,
                Session.status == SessionStatus.ACTIVE,
            )
            .values(status=SessionStatus.REVOKED, revoked_at=now)
        )
        await self.session.execute(
            update(OfflineLicense)
            .where(
                OfflineLicense.user_id == user_id,
                OfflineLicense.revoked.is_(False),
            )
            .values(revoked=True, revoked_at=now)
        )
        await self.audit(
            actor_id=admin_id,
            action="users.suspend",
            target_type="user",
            target_id=str(user_id),
            before=before,
            after={"status": UserStatus.SUSPENDED.value},
            reason=reason,
        )
        await self.session.flush()
        return user

    async def unsuspend_user(self, user_id: UUID, admin_id: UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        user.status = UserStatus.ACTIVE
        await self.audit(
            actor_id=admin_id,
            action="users.unsuspend",
            target_type="user",
            target_id=str(user_id),
            after={"status": UserStatus.ACTIVE.value},
        )
        await self.session.flush()
        return user

    # --- Feature flags ---

    async def ensure_default_flags(self) -> None:
        for key, enabled in DEFAULT_FLAGS.items():
            existing = await self.session.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
            if existing is None:
                self.session.add(FeatureFlag(key=key, enabled=enabled, description=f"Flag: {key}"))
        await self.session.flush()

    async def list_flags(self) -> list[FeatureFlag]:
        result = await self.session.execute(select(FeatureFlag).order_by(FeatureFlag.key))
        return list(result.scalars().all())

    async def set_flag(self, key: str, enabled: bool, admin_id: UUID) -> FeatureFlag:
        flag = await self.session.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
        if flag is None:
            flag = FeatureFlag(key=key, enabled=enabled)
            self.session.add(flag)
        else:
            before = {"enabled": flag.enabled}
            flag.enabled = enabled
            flag.updated_by = admin_id
            await self.audit(
                actor_id=admin_id,
                action="feature_flags.write",
                target_type="feature_flag",
                target_id=key,
                before=before,
                after={"enabled": enabled},
            )
        await self.session.flush()
        return flag

    async def get_setting(self, key: str) -> SystemSetting | None:
        return await self.session.scalar(select(SystemSetting).where(SystemSetting.key == key))

    async def set_setting(
        self, key: str, value: dict[str, Any], admin_id: UUID, *, description: str | None = None
    ) -> SystemSetting:
        setting = await self.get_setting(key)
        if setting is None:
            setting = SystemSetting(key=key, value=value, description=description)
            self.session.add(setting)
        else:
            before = dict(setting.value)
            setting.value = value
            setting.updated_by = admin_id
            await self.audit(
                actor_id=admin_id,
                action="settings.write",
                target_type="system_setting",
                target_id=key,
                before=before,
                after=value,
            )
        await self.session.flush()
        return setting

    async def is_maintenance_mode(self) -> bool:
        flag = await self.session.scalar(
            select(FeatureFlag).where(FeatureFlag.key == "maintenance_mode")
        )
        return bool(flag and flag.enabled)
