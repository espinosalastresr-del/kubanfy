"""FastAPI dependencies: auth, permissions, DB session helpers."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_token
from app.models.rbac import Role, UserRole
from app.models.user import User, UserStatus

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
    result = await session.execute(
        select(UserRole)
        .where(UserRole.user_id == user_id)
        .options(selectinload(UserRole.role).selectinload(Role.permissions))
    )
    user_roles = result.scalars().all()
    codes: set[str] = set()
    for ur in user_roles:
        if ur.role and ur.role.permissions:
            for perm in ur.role.permissions:
                codes.add(perm.code)
    return codes


def require_permissions(*required: str):
    """Dependency factory: require ALL listed permission codes."""

    async def _checker(
        user: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        if not required:
            return user
        codes = await get_user_permission_codes(user.id, session)
        missing = [p for p in required if p not in codes]
        if missing:
            raise ForbiddenError(
                "Insufficient permissions",
                details={"missing": missing},
            )
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
        codes = await get_user_permission_codes(user.id, session)
        if not any(p in codes for p in required):
            raise ForbiddenError(
                "Insufficient permissions",
                details={"required_any": list(required)},
            )
        return user

    return _checker


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
