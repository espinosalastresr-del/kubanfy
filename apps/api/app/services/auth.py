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
from app.models.artist_member import ArtistMember
from app.models.device import Device, SessionStatus
from app.models.rbac import Role, UserRole
from app.models.user import User, UserStatus
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.device_identity import DeviceIdentityService
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
        if not user.email_verified or user.status == UserStatus.PENDING_VERIFICATION:
            raise AuthError(
                "Email verification required",
                code="EMAIL_NOT_VERIFIED",
                status_code=403,
            )

        user.last_login_at = datetime.now(UTC)

        device = None
        if data.device_id:
            if not all((data.device_public_key, data.identity_challenge_id, data.identity_signature)):
                raise AuthError("This device must prove its cryptographic identity before login", code="DEVICE_PROOF_REQUIRED")
            proven_public_key = await DeviceIdentityService(self.session).verify_login_challenge(
                data.device_id, data.identity_challenge_id, data.identity_signature, data.device_public_key
            )
            device = await self.sessions.register_or_update_device(
                user.id, data.device_id, name=data.device_name,
                platform=data.platform, public_key=proven_public_key,
            )

        tokens, jti, access_jti = self._issue_tokens(user, device_id=data.device_id)
        await self.sessions.create_session(
            user.id,
            jti,
            access_token_jti=access_jti,
            device=device,
            ip_country=ip_country,
            user_agent=user_agent,
        )
        await self.session.flush()
        logger.info("user_logged_in", user_id=str(user.id))
        return user, tokens

    async def create_refresh_challenge(self, refresh_token: str, *, device_id: str) -> dict[str, str | int]:
        """Create a proof challenge without extending the session idle timeout."""
        try:
            payload = decode_token(refresh_token, self.settings)
        except ValueError as exc:
            raise AuthError("Invalid or expired refresh token") from exc
        if payload.get("type") != "refresh":
            raise AuthError("Invalid token type")
        jti = payload.get("jti")
        if not jti:
            raise AuthError("Invalid refresh token")
        sess = await self.sessions.validate_refresh_session(jti, touch_activity=False)
        if payload.get("sub") != str(sess.user_id) or sess.device_id is None:
            raise AuthError("Refresh token is not bound to this device", code="DEVICE_IDENTITY_REQUIRED")
        device = await self.session.get(Device, sess.device_id)
        if device is None or device.device_id != device_id or payload.get("device_id") != device.device_id:
            raise AuthError("Refresh device mismatch")
        return await DeviceIdentityService(self.session).create_refresh_challenge(sess.user_id, sess, jti, device)

    async def refresh(
        self, refresh_token: str, *, device_id: str | None = None,
        challenge_id: str | None = None, signature: str | None = None,
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
        sess = await self.sessions.validate_refresh_session(jti, touch_activity=False)
        if payload.get("sub") != str(sess.user_id):
            raise AuthError("Refresh token subject mismatch")
        token_device_id = payload.get("device_id")
        if sess.device_id is not None:
            device = await self.session.get(Device, sess.device_id)
            if device is None or device.device_id != token_device_id or device.device_id != device_id:
                raise AuthError("Refresh device mismatch")
            sess.device = device
            if not challenge_id or not signature:
                raise AuthError("A signed device proof is required to rotate this refresh token", code="DEVICE_PROOF_REQUIRED")
            await DeviceIdentityService(self.session).verify_refresh_challenge(
                sess.user_id, sess, jti, device, challenge_id, signature
            )
        elif token_device_id or device_id:
            raise AuthError(
                "The refresh token references a device that is no longer bound to this session",
                code="DEVICE_IDENTITY_REQUIRED",
            )
        elif challenge_id or signature:
            raise AuthError("Unexpected device proof for an unbound session")
        sess.last_activity_at = datetime.now(UTC)
        user = await self.session.get(User, sess.user_id)
        if user is None or user.status in (UserStatus.SUSPENDED, UserStatus.DELETED):
            raise AuthError("Account not available")
        if not user.email_verified or user.status == UserStatus.PENDING_VERIFICATION:
            raise AuthError(
                "Email verification required",
                code="EMAIL_NOT_VERIFIED",
                status_code=403,
            )

        # Rotate: revoke old session, issue new tokens + session
        sess.status = SessionStatus.REVOKED
        sess.revoked_at = datetime.now(UTC)

        bound_device_id = token_device_id or (sess.device.device_id if sess.device else None)
        if device_id and sess.device is not None and device_id != sess.device.device_id:
            raise AuthError("Refresh device mismatch")
        tokens, new_jti, access_jti = self._issue_tokens(user, device_id=bound_device_id)
        await self.sessions.create_session(
            user.id,
            new_jti,
            access_token_jti=access_jti,
            device=sess.device,
            ip_country=sess.ip_country,
            user_agent=sess.user_agent,
        )
        await self.session.flush()
        logger.info("token_refreshed", user_id=str(user.id))
        return tokens

    def _issue_tokens(
        self, user: User, device_id: str | None = None
    ) -> tuple[TokenResponse, str, str]:
        access = create_access_token(
            str(user.id),
            extra_claims={
                "email": user.email,
                "status": user.status.value,
                **({"device_id": device_id} if device_id else {}),
            },
            settings=self.settings,
        )
        refresh = create_refresh_token(
            str(user.id),
            device_id=device_id,
            settings=self.settings,
        )
        # Bind both bearer tokens to the same persisted session.
        access_payload = decode_token(access, self.settings)
        refresh_payload = decode_token(refresh, self.settings)
        access_jti = access_payload["jti"]
        jti = refresh_payload["jti"]
        tokens = TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )
        return tokens, jti, access_jti

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_access_context(self, user_id: UUID) -> tuple[list[str], list[UUID]]:
        role_rows = await self.session.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.name)
        )
        roles = list(role_rows.scalars().all())
        artist_rows = await self.session.execute(
            select(ArtistMember.artist_id)
            .where(ArtistMember.user_id == user_id)
            .order_by(ArtistMember.artist_id)
        )
        artist_ids = list(artist_rows.scalars().all())
        return roles, artist_ids

    @staticmethod
    def to_response(user: User) -> UserResponse:
        return UserResponse.model_validate(user)
