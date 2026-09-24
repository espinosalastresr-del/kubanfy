"""Device and session management service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.device import Device, DeviceStatus, Session, SessionStatus
from app.models.offline import OfflineLicense
from app.models.user import User

logger = get_logger(__name__)


class SessionService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.db = session
        self.settings = settings or get_settings()

    async def register_or_update_device(
        self,
        user_id: UUID,
        device_id: str,
        *,
        name: str | None = None,
        platform: str | None = None,
        os_version: str | None = None,
        app_version: str | None = None,
    ) -> Device:
        """Get or create device. Enforce max devices limit."""
        # Serialize per-user device creation so concurrent registrations cannot
        # bypass the configured device limit or create duplicate device identities.
        await self.db.scalar(select(User).where(User.id == user_id).with_for_update())
        existing = await self.db.scalar(
            select(Device).where(
                Device.user_id == user_id,
                Device.device_id == device_id,
            )
        )
        now = datetime.now(UTC)

        if existing is not None:
            if existing.status == DeviceStatus.REVOKED:
                raise ForbiddenError("This device has been revoked")
            existing.last_seen_at = now
            if name:
                existing.name = name
            if platform:
                existing.platform = platform
            if os_version:
                existing.os_version = os_version
            if app_version:
                existing.app_version = app_version
            await self.db.flush()
            return existing

        # Count active devices
        active_count = await self.db.scalar(
            select(func.count())
            .select_from(Device)
            .where(
                Device.user_id == user_id,
                Device.status == DeviceStatus.ACTIVE,
            )
        )
        if active_count is not None and active_count >= self.settings.max_devices_per_user:
            raise ForbiddenError(
                f"Maximum number of devices ({self.settings.max_devices_per_user}) reached. "
                "Revoke an existing device first."
            )

        device = Device(
            user_id=user_id,
            device_id=device_id,
            name=name,
            platform=platform,
            os_version=os_version,
            app_version=app_version,
            status=DeviceStatus.ACTIVE,
            last_seen_at=now,
        )
        self.db.add(device)
        await self.db.flush()
        logger.info("device_registered", user_id=str(user_id), device_id=device_id)
        return device

    async def create_session(
        self,
        user_id: UUID,
        refresh_token_jti: str,
        *,
        device: Device | None = None,
        ip_country: str | None = None,
        user_agent: str | None = None,
    ) -> Session:
        """Create a new session. Enforce concurrent session limit."""
        # Serialize per-user session creation so concurrent logins cannot bypass
        # the configured concurrent-session limit.
        await self.db.scalar(select(User).where(User.id == user_id).with_for_update())
        active_count = await self.db.scalar(
            select(func.count())
            .select_from(Session)
            .where(
                Session.user_id == user_id,
                Session.status == SessionStatus.ACTIVE,
            )
        )
        if active_count is not None and active_count >= self.settings.max_concurrent_sessions:
            # Revoke oldest active session
            oldest = await self.db.scalar(
                select(Session)
                .where(
                    Session.user_id == user_id,
                    Session.status == SessionStatus.ACTIVE,
                )
                .order_by(Session.created_at.asc())
                .limit(1)
            )
            if oldest:
                oldest.status = SessionStatus.REVOKED
                oldest.revoked_at = datetime.now(UTC)
                logger.info(
                    "session_revoked_limit",
                    user_id=str(user_id),
                    session_id=str(oldest.id),
                )

        expires_at = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_expire_days)
        sess = Session(
            user_id=user_id,
            device_id=device.id if device else None,
            refresh_token_jti=refresh_token_jti,
            status=SessionStatus.ACTIVE,
            ip_country=ip_country,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        self.db.add(sess)
        await self.db.flush()
        return sess

    async def get_session_by_jti(self, jti: str, *, for_update: bool = False) -> Session | None:
        stmt = select(Session).where(Session.refresh_token_jti == jti)
        if for_update:
            stmt = stmt.with_for_update()
        return await self.db.scalar(stmt)

    async def revoke_session(self, session_id: UUID, user_id: UUID) -> None:
        sess = await self.db.get(Session, session_id)
        if sess is None or sess.user_id != user_id:
            raise NotFoundError("Session not found")
        sess.status = SessionStatus.REVOKED
        sess.revoked_at = datetime.now(UTC)
        await self.db.flush()
        logger.info("session_revoked", session_id=str(session_id), user_id=str(user_id))

    async def revoke_all_sessions(self, user_id: UUID, *, except_jti: str | None = None) -> int:
        q = (
            update(Session)
            .where(
                Session.user_id == user_id,
                Session.status == SessionStatus.ACTIVE,
            )
            .values(status=SessionStatus.REVOKED, revoked_at=datetime.now(UTC))
        )
        if except_jti:
            q = q.where(Session.refresh_token_jti != except_jti)
        result = await self.db.execute(q)
        await self.db.flush()
        count = result.rowcount or 0
        logger.info("sessions_revoked_all", user_id=str(user_id), count=count)
        return count

    async def list_devices(self, user_id: UUID) -> list[Device]:
        result = await self.db.execute(
            select(Device).where(Device.user_id == user_id).order_by(Device.last_seen_at.desc())
        )
        return list(result.scalars().all())

    async def list_sessions(self, user_id: UUID) -> list[Session]:
        result = await self.db.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.last_activity_at.desc())
        )
        return list(result.scalars().all())

    async def revoke_device(self, device_db_id: UUID, user_id: UUID) -> None:
        device = await self.db.get(Device, device_db_id)
        if device is None or device.user_id != user_id:
            raise NotFoundError("Device not found")
        device.status = DeviceStatus.REVOKED
        device.revoked_at = datetime.now(UTC)
        # Revoke all sessions and offline licenses bound to this device.
        await self.db.execute(
            update(Session)
            .where(
                Session.device_id == device.id,
                Session.status == SessionStatus.ACTIVE,
            )
            .values(status=SessionStatus.REVOKED, revoked_at=datetime.now(UTC))
        )
        await self.db.execute(
            update(OfflineLicense)
            .where(
                OfflineLicense.device_id == device.id,
                OfflineLicense.revoked.is_(False),
            )
            .values(revoked=True, revoked_at=datetime.now(UTC))
        )
        await self.db.flush()
        logger.info("device_revoked", device_id=str(device_db_id), user_id=str(user_id))

    async def validate_refresh_session(self, jti: str) -> Session:
        """Validate that a refresh token jti corresponds to an active, non-expired session."""
        sess = await self.get_session_by_jti(jti, for_update=True)
        if sess is None:
            raise AuthError("Invalid refresh token")
        if sess.status != SessionStatus.ACTIVE:
            raise AuthError("Session has been revoked")
        now = datetime.now(UTC)
        expires_at = (
            sess.expires_at
            if sess.expires_at.tzinfo is not None
            else sess.expires_at.replace(tzinfo=UTC)
        )
        last_activity_at = (
            sess.last_activity_at
            if sess.last_activity_at.tzinfo is not None
            else sess.last_activity_at.replace(tzinfo=UTC)
        )
        if expires_at <= now:
            sess.status = SessionStatus.EXPIRED
            await self.db.flush()
            raise AuthError("Session expired")
        if last_activity_at + timedelta(minutes=self.settings.session_idle_timeout_minutes) <= now:
            sess.status = SessionStatus.EXPIRED
            await self.db.flush()
            raise AuthError("Session idle timeout")
        sess.last_activity_at = now
        await self.db.flush()
        return sess
