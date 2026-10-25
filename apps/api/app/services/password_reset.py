"""Password reset workflow with hashed, expiring, single-use tokens."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.device import SessionStatus
from app.models.password_reset import PasswordResetToken
from app.models.user import User, UserStatus
from app.services.email_delivery import EmailDeliveryService

logger = get_logger(__name__)


class PasswordResetService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        email_delivery: EmailDeliveryService | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.email_delivery = email_delivery or EmailDeliveryService(self.settings)

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def request_reset(self, email: str) -> None:
        normalized = email.strip().lower()
        user = await self.session.scalar(select(User).where(User.email == normalized))
        if user is None or user.status in (UserStatus.DELETED, UserStatus.SUSPENDED):
            return

        now = datetime.now(UTC)
        # Invalidate any earlier unconsumed links before issuing a new one.
        await self.session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        raw_token = secrets.token_urlsafe(32)
        record = PasswordResetToken(
            user_id=user.id,
            token_hash=self._digest(raw_token),
            expires_at=now + timedelta(minutes=self.settings.password_reset_token_expire_minutes),
        )
        self.session.add(record)
        await self.session.flush()

        # Do not expose tokens in API responses or logs. If delivery is
        # misconfigured, log only the provider error and preserve enumeration resistance.
        reset_url = f"{self.settings.frontend_base_url.rstrip('/')}/#reset_token={quote(raw_token)}"
        try:
            await self.email_delivery.send(
                user.email,
                "Restablece tu contraseña de KubanFy",
                "Recibimos una solicitud para cambiar tu contraseña. Abre este enlace para continuar: "
                f"{reset_url}\nSi no lo solicitaste, ignora este correo.",
                "<p>Recibimos una solicitud para cambiar tu contraseña de KubanFy.</p>"
                f'<p><a href="{reset_url}">Crear una nueva contraseña</a></p>'
                "<p>Si no lo solicitaste, ignora este correo.</p>",
            )
        except Exception as exc:
            logger.error("password_reset_email_failed", provider=self.settings.email_provider.value, error=type(exc).__name__)

    async def consume(self, token: str, new_password: str) -> bool:
        now = datetime.now(UTC)
        digest = self._digest(token)
        record = await self.session.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == digest)
            .with_for_update()
        )
        if record is None or record.used_at is not None or record.expires_at <= now:
            return False

        user = await self.session.get(User, record.user_id)
        if user is None or user.status in (UserStatus.DELETED, UserStatus.SUSPENDED):
            record.used_at = now
            return False

        user.password_hash = hash_password(new_password)
        record.used_at = now
        # Password reset terminates all existing refresh sessions.
        from app.models.device import Session

        await self.session.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.status == SessionStatus.ACTIVE)
            .values(status=SessionStatus.REVOKED, revoked_at=now)
        )
        await self.session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.id != record.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        await self.session.flush()
        return True
