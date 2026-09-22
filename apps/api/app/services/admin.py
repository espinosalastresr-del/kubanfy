"""Admin service: audit logging, moderation, feature flags, settings, user suspend."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
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

    # --- Users ---

    async def suspend_user(self, user_id: UUID, admin_id: UUID, *, reason: str | None = None) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        before = {"status": user.status.value}
        user.status = UserStatus.SUSPENDED
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
            existing = await self.session.scalar(
                select(FeatureFlag).where(FeatureFlag.key == key)
            )
            if existing is None:
                self.session.add(
                    FeatureFlag(key=key, enabled=enabled, description=f"Flag: {key}")
                )
        await self.session.flush()

    async def list_flags(self) -> list[FeatureFlag]:
        result = await self.session.execute(select(FeatureFlag).order_by(FeatureFlag.key))
        return list(result.scalars().all())

    async def set_flag(
        self, key: str, enabled: bool, admin_id: UUID
    ) -> FeatureFlag:
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
        return await self.session.scalar(
            select(SystemSetting).where(SystemSetting.key == key)
        )

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
