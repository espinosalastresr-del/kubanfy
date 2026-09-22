"""Authentication and registration service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthError, ConflictError, ValidationError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserStatus
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

logger = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

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

    async def login(self, data: LoginRequest) -> tuple[User, TokenResponse]:
        user = await self.session.scalar(select(User).where(User.email == data.email.lower()))
        if user is None or not verify_password(data.password, user.password_hash):
            logger.warning("login_failed", email=data.email.lower())
            raise AuthError("Invalid email or password")

        if user.status == UserStatus.SUSPENDED:
            raise AuthError("Account is suspended")
        if user.status == UserStatus.DELETED:
            raise AuthError("Account not found")

        user.last_login_at = datetime.now(UTC)
        await self.session.flush()

        tokens = self._issue_tokens(user, device_id=data.device_id)
        logger.info("user_logged_in", user_id=str(user.id))
        return user, tokens

    def _issue_tokens(self, user: User, device_id: str | None = None) -> TokenResponse:
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
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    @staticmethod
    def to_response(user: User) -> UserResponse:
        return UserResponse.model_validate(user)
