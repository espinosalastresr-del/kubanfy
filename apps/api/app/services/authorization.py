"""Centralized global RBAC and artist-scoped authorization."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.artist_member import ArtistMember, ArtistMemberRole
from app.models.music import Artist
from app.models.rbac import Role, UserRole


class AuthorizationService:
    """Evaluate global permissions and resource-scoped artist membership."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_permission_codes(self, user_id: UUID) -> set[str]:
        """Return the union of permission codes granted through system roles."""
        result = await self.session.execute(
            select(UserRole)
            .where(UserRole.user_id == user_id)
            .options(selectinload(UserRole.role).selectinload(Role.permissions))
        )
        codes: set[str] = set()
        for user_role in result.scalars().all():
            if user_role.role is not None:
                codes.update(permission.code for permission in user_role.role.permissions or [])
        return codes

    async def has_all_permissions(self, user_id: UUID, required: list[str] | tuple[str, ...]) -> bool:
        if not required:
            return True
        granted = await self.get_permission_codes(user_id)
        return all(code in granted for code in required)

    async def has_any_permission(self, user_id: UUID, required: list[str] | tuple[str, ...]) -> bool:
        if not required:
            return True
        granted = await self.get_permission_codes(user_id)
        return any(code in granted for code in required)

    async def require_all_permissions(
        self, user_id: UUID, required: list[str] | tuple[str, ...]
    ) -> None:
        granted = await self.get_permission_codes(user_id)
        missing = [code for code in required if code not in granted]
        if missing:
            raise ForbiddenError("Insufficient permissions", details={"missing": missing})

    async def require_any_permission(
        self, user_id: UUID, required: list[str] | tuple[str, ...]
    ) -> None:
        if required and not await self.has_any_permission(user_id, required):
            raise ForbiddenError(
                "Insufficient permissions",
                details={"required_any": list(required)},
            )

    async def require_artist_roles(
        self,
        user_id: UUID,
        artist_id: UUID,
        allowed_roles: set[ArtistMemberRole] | frozenset[ArtistMemberRole],
        *,
        hide_existence: bool = True,
        require_active_artist: bool = False,
        denial_message: str = "Insufficient artist permissions",
    ) -> ArtistMember:
        """Require membership in an allowed role, optionally requiring an active artist.

        Artist-scoped checks deliberately do not infer authorization from client
        context or from a global UI role. Callers that need global system access
        must check an explicit system permission separately.
        """
        if require_active_artist:
            artist = await self.session.scalar(select(Artist).where(Artist.id == artist_id))
            if artist is None or artist.status != "active":
                if hide_existence:
                    raise NotFoundError("Artist not found")
                raise ForbiddenError(denial_message)

        member = await self.session.scalar(
            select(ArtistMember).where(
                ArtistMember.artist_id == artist_id,
                ArtistMember.user_id == user_id,
            )
        )

        if member is None or member.role not in allowed_roles:
            if hide_existence:
                raise NotFoundError("Artist not found")
            raise ForbiddenError(denial_message)
        return member
