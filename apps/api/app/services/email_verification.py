"""Email ownership verification with hashed, expiring, single-use tokens."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from html import escape
from urllib.parse import quote

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.email_verification import EmailVerificationToken
from app.models.user import User, UserStatus
from app.services.email_delivery import EmailDeliveryService

logger = get_logger(__name__)


class EmailVerificationService:
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

    async def send_for_user(self, user: User) -> None:
        if user.email_verified or user.status in (UserStatus.SUSPENDED, UserStatus.DELETED):
            return

        now = datetime.now(UTC)
        await self.session.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        raw_token = secrets.token_urlsafe(32)
        record = EmailVerificationToken(
            user_id=user.id,
            token_hash=self._digest(raw_token),
            expires_at=now + timedelta(hours=self.settings.email_verification_token_expire_hours),
        )
        self.session.add(record)
        await self.session.flush()

        verify_url = (
            f"{self.settings.frontend_base_url.rstrip('/')}/"
            f"?verify_token={quote(raw_token, safe='')}"
        )
        safe_url = escape(verify_url, quote=True)
        text_body = (
            "Confirma tu correo electrónico para activar tu cuenta de KubanFy. "
            f"Abre este enlace: {verify_url}\n"
            "Si no creaste esta cuenta, puedes ignorar este mensaje."
        )
        html_body = (
            "<p>Confirma tu correo electrónico para activar tu cuenta de KubanFy.</p>"
            f'<p><a href="{safe_url}">Verificar mi correo</a></p>'
            f"<p>Si el enlace no funciona, copia esta dirección: {safe_url}</p>"
            "<p>Si no creaste esta cuenta, puedes ignorar este mensaje.</p>"
        )
        try:
            await self.email_delivery.send(
                user.email,
                "Confirma tu correo electrónico — KubanFy",
                text_body,
                html_body,
            )
        except Exception as exc:
            record.used_at = datetime.now(UTC)
            await self.session.flush()
            logger.error(
                "email_verification_delivery_failed",
                provider=self.settings.email_provider.value,
                error=type(exc).__name__,
            )

    async def request_for_email(self, email: str) -> None:
        normalized = email.strip().lower()
        user = await self.session.scalar(select(User).where(User.email == normalized))
        if user is None or user.email_verified:
            return
        await self.send_for_user(user)

    async def consume(self, token: str) -> bool:
        now = datetime.now(UTC)
        record = await self.session.scalar(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.token_hash == self._digest(token))
            .with_for_update()
        )
        if record is None or record.used_at is not None or record.expires_at <= now:
            return False

        user = await self.session.get(User, record.user_id)
        if user is None or user.status in (UserStatus.DELETED, UserStatus.SUSPENDED):
            record.used_at = now
            await self.session.flush()
            return False

        record.used_at = now
        user.email_verified = True
        if user.status == UserStatus.PENDING_VERIFICATION:
            user.status = UserStatus.ACTIVE

        await self.session.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.id != record.id,
                EmailVerificationToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        await self.session.flush()
        return True
