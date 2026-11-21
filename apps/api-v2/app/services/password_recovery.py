import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import httpx
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, hash_session_token
from app.models import PasswordResetToken, User, UserSession
from app.schemas.auth import PasswordResetRequest

logger = logging.getLogger(__name__)
RECOVERY_MESSAGE = (
    "Si la dirección corresponde a una cuenta activa y el correo está configurado, "
    "recibirás instrucciones para restablecer la contraseña."
)


def recovery_email_is_configured() -> bool:
    return bool(
        settings.email_provider == "resend"\n        and settings.email_provider_api_key.strip()
        and settings.email_from.strip()
        and settings.auth_web_url.strip()
    )


async def request_password_reset(db: AsyncSession, email: str) -> None:
    # Deliberately return the same result for unknown, inactive, and known accounts.
    if not recovery_email_is_configured():
        return

    user = await db.scalar(
        select(User).where(User.email == email.strip().lower(), User.is_active.is_(True))
    )
    if user is None:
        return

    raw_token = secrets.token_urlsafe(48)
    record = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_minutes),
    )
    await db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    db.add(record)
    await db.commit()

    reset_url = settings.auth_web_url.rstrip("/") + "/?token=" + quote(raw_token, safe="")
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.email_provider_api_key.strip()}"},
                json={
                    "from": settings.email_from.strip(),
                    "to": [user.email],
                    "subject": "Restablece tu contraseña de KubanFy",
                    "html": (
                        "<p>Recibimos una solicitud para restablecer tu contraseña de KubanFy.</p>"
                        f'<p><a href="{reset_url}">Crear nueva contraseña</a></p>'
                        f"<p>Este enlace caduca en {settings.password_reset_minutes} minutos. "
                        "Si no solicitaste el cambio, ignora este correo.</p>"
                    ),
                },
            )
            response.raise_for_status()
    except (httpx.HTTPError, ValueError):
        # Do not expose provider errors or account existence to the caller.
        record.used_at = datetime.now(UTC)
        await db.commit()
        logger.warning("Password recovery email delivery failed; provider response suppressed.")


async def reset_user_password(db: AsyncSession, payload: PasswordResetRequest) -> None:
    now = datetime.now(UTC)
    record = await db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hash_session_token(payload.token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .with_for_update()
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de recuperación no es válido o ha caducado.",
        )

    user = await db.scalar(
        select(User).where(User.id == record.user_id, User.is_active.is_(True)).with_for_update()
    )
    if user is None:
        record.used_at = now
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de recuperación no es válido o ha caducado.",
        )

    user.password_hash = hash_password(payload.password)
    record.used_at = now
    await db.execute(
        delete(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
        )
    )
    await db.commit()
