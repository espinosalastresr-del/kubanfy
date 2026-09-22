"""Authentication and registration service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthError, ConflictError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.device import SessionStatus
from app.models.user import User, UserStatus
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.session import SessionService

logger = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.sessions = SessionService(session, self.settings)

    async def register(self, data: RegisterRequest) -> User:
        existing = await self.session.scalar(select(User).where(User.email == data.email.lower()))
        if existing is not None:
            raise ConflictError("Email already registered")

        country = data.country or self.settings.default_country
        user = User(
            email=data.email.lower(),
            password_hash=hash_password(data.password),
            display_name=data.display_name.strip(),
            country=country.upper(),
            country_source="user_selected" if data.country else "default",
            language=data.language,
            status=UserStatus.PENDING_VERIFICATION,
            email_verified=False,
        )
        self.session.add(user)
        await self.session.flush()
        logger.info("user_registered", user_id=str(user.id), email=user.email)
        return user

    async def login(
        self,
        data: LoginRequest,
        *,
        ip_country: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, TokenResponse]:
        user = await self.session.scalar(select(User).where(User.email == data.email.lower()))
        if user is None or not verify_password(data.password, user.password_hash):
            logger.warning("login_failed", email=data.email.lower())
            raise AuthError("Invalid email or password")

        if user.status == UserStatus.SUSPENDED:
            raise AuthError("Account is suspended")
        if user.status == UserStatus.DELETED:
            raise AuthError("Account not found")

        user.last_login_at = datetime.now(UTC)

        device = None
        if data.device_id:
            device = await self.sessions.register_or_update_device(
                user.id,
                data.device_id,
                name=data.device_name,
                platform=data.platform,
            )

        tokens, jti = self._issue_tokens(user, device_id=data.device_id)
        await self.sessions.create_session(
            user.id,
            jti,
            device=device,
            ip_country=ip_country,
            user_agent=user_agent,
        )
        await self.session.flush()
        logger.info("user_logged_in", user_id=str(user.id))
        return user, tokens

    async def refresh(
        self,
        refresh_token: str,
        *,
        device_id: str | None = None,
    ) -> TokenResponse:
        try:
            payload = decode_token(refresh_token, self.settings)
        except ValueError as exc:
            raise AuthError("Invalid or expired refresh token") from exc

        if payload.get("type") != "refresh":
            raise AuthError("Invalid token type")

        jti = payload.get("jti")
        if not jti:
            raise AuthError("Invalid refresh token")

        sess = await self.sessions.validate_refresh_session(jti)
        user = await self.session.get(User, sess.user_id)
        if user is None or user.status in (UserStatus.SUSPENDED, UserStatus.DELETED):
            raise AuthError("Account not available")

        # Rotate: revoke old session, issue new tokens + session
        sess.status = SessionStatus.REVOKED
        sess.revoked_at = datetime.now(UTC)

        tokens, new_jti = self._issue_tokens(user, device_id=device_id or payload.get("device_id"))
        await self.sessions.create_session(
            user.id,
            new_jti,
            device=sess.device,
            ip_country=sess.ip_country,
            user_agent=sess.user_agent,
        )
        await self.session.flush()
        logger.info("token_refreshed", user_id=str(user.id))
        return tokens

    def _issue_tokens(
        self, user: User, device_id: str | None = None
    ) -> tuple[TokenResponse, str]:
        access = create_access_token(
            str(user.id),
            extra_claims={"email": user.email, "status": user.status.value},
            settings=self.settings,
        )
        refresh = create_refresh_token(
            str(user.id),
            device_id=device_id,
            settings=self.settings,
        )
        # Extract jti from refresh token
        refresh_payload = decode_token(refresh, self.settings)
        jti = refresh_payload["jti"]
        tokens = TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )
        return tokens, jti

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    @staticmethod
    def to_response(user: User) -> UserResponse:
        return UserResponse.model_validate(user)
