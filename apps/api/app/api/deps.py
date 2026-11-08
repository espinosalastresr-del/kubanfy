"""FastAPI dependencies: auth, permissions, DB session helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthError
from app.core.security import decode_token
from app.models.device import Session, SessionStatus
from app.models.user import User, UserStatus
from app.services.authorization import AuthorizationService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Require a valid access token and return the active user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthError("Missing or invalid authorization header")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise AuthError("Invalid or expired token") from exc

    if payload.get("type") != "access":
        raise AuthError("Invalid token type")

    sub = payload.get("sub")
    if not sub:
        raise AuthError("Invalid token subject")

    try:
        user_id = UUID(sub)
    except ValueError as exc:
        raise AuthError("Invalid token subject") from exc

    user = await session.get(User, user_id)
    if user is None:
        raise AuthError("User not found")
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

    # Access tokens are bound to the persisted session. Revoking a session or
    # its device therefore invalidates already-issued access tokens immediately.
    access_jti = payload.get("jti")
    if not isinstance(access_jti, str) or not access_jti:
        raise AuthError("Invalid access token session", code="SESSION_INVALID")
    auth_session = await session.scalar(
        select(Session).where(
            Session.access_token_jti == access_jti,
            Session.user_id == user_id,
        )
    )
    if auth_session is None or auth_session.status != SessionStatus.ACTIVE:
        raise AuthError("Session has been revoked", code="SESSION_INVALID")

    now = datetime.now(UTC)
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    last_activity_at = auth_session.last_activity_at
    if last_activity_at.tzinfo is None:
        last_activity_at = last_activity_at.replace(tzinfo=UTC)
    if expires_at <= now:
        raise AuthError("Session expired", code="SESSION_EXPIRED")
    if last_activity_at + timedelta(minutes=get_settings().session_idle_timeout_minutes) <= now:
        raise AuthError("Session idle timeout", code="SESSION_EXPIRED")

    # Avoid a write on every API request while keeping idle-session activity
    # accurate enough for the configured 60-minute timeout.
    if last_activity_at <= now - timedelta(minutes=5):
        auth_session.last_activity_at = now

    return user


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Return current user if token present and valid, else None."""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, session)
    except AuthError:
        return None


async def get_user_permission_codes(
    user_id: UUID,
    session: AsyncSession,
) -> set[str]:
    """Load all permission codes granted to a user via their roles."""
    return await AuthorizationService(session).get_permission_codes(user_id)


def require_permissions(*required: str):
    """Dependency factory: require ALL listed permission codes."""

    async def _checker(
        user: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        if not required:
            return user
        await AuthorizationService(session).require_all_permissions(user.id, required)
        return user

    return _checker


def require_any_permission(*required: str):
    """Dependency factory: require AT LEAST ONE of the listed permission codes."""

    async def _checker(
        user: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        if not required:
            return user
        await AuthorizationService(session).require_any_permission(user.id, required)
        return user

    return _checker


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
