"""RBAC service: roles, permissions, assignment.

Permission codes follow the plan (section 61):
  users.read, users.write, users.suspend
  artists.read, artists.write, artists.approve
  tracks.read, tracks.write, tracks.publish, tracks.takedown
  payments.read, payments.verify, payments.refund
  analytics.read, analytics.export
  providers.read, providers.configure, providers.disable
  cache.read, cache.purge
  jobs.read, jobs.retry, jobs.cancel
  security.read, security.enforce
  settings.read, settings.write
  feature_flags.read, feature_flags.write
  audit_logs.read, audit_logs.export
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.rbac import Permission, Role, SystemRole, UserRole

logger = get_logger(__name__)

# Default permission catalog (code -> description)
DEFAULT_PERMISSIONS: dict[str, str] = {
    "users.read": "View users",
    "users.write": "Create/update users",
    "users.suspend": "Suspend users",
    "artists.read": "View artists",
    "artists.write": "Create/update artists",
    "artists.approve": "Approve artists",
    "tracks.read": "View tracks",
    "tracks.write": "Create/update tracks",
    "tracks.publish": "Publish tracks",
    "tracks.takedown": "Takedown tracks",
    "payments.read": "View payments",
    "payments.verify": "Verify payments",
    "payments.refund": "Refund payments",
    "royalties.read": "View royalty accounting",
    "royalties.write": "Write royalty accounting",
    "analytics.read": "View analytics",
    "analytics.export": "Export analytics",
    "providers.read": "View providers",
    "providers.configure": "Configure providers",
    "providers.disable": "Disable providers",
    "cache.read": "View cache status",
    "cache.purge": "Purge cache",
    "jobs.read": "View jobs",
    "jobs.retry": "Retry jobs",
    "jobs.cancel": "Cancel jobs",
    "security.read": "View security events",
    "security.enforce": "Enforce security actions",
    "settings.read": "View system settings",
    "settings.write": "Modify system settings",
    "feature_flags.read": "View feature flags",
    "feature_flags.write": "Modify feature flags",
    "audit_logs.read": "View audit logs",
    "audit_logs.export": "Export audit logs",
}

# Role -> list of permission codes
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    SystemRole.SUPER_ADMIN.value: list(DEFAULT_PERMISSIONS.keys()),
    SystemRole.ADMIN.value: [
        "users.read",
        "users.write",
        "users.suspend",
        "artists.read",
        "artists.write",
        "artists.approve",
        "tracks.read",
        "tracks.write",
        "tracks.publish",
        "tracks.takedown",
        "payments.read",
        "payments.verify",
        "analytics.read",
        "analytics.export",
        "providers.read",
        "providers.configure",
        "cache.read",
        "cache.purge",
        "jobs.read",
        "jobs.retry",
        "jobs.cancel",
        "security.read",
        "security.enforce",
        "settings.read",
        "settings.write",
        "feature_flags.read",
        "feature_flags.write",
        "audit_logs.read",
        "audit_logs.export",
    ],
    SystemRole.MODERATOR.value: [
        "users.read",
        "artists.read",
        "tracks.read",
        "tracks.takedown",
        "analytics.read",
        "security.read",
        "audit_logs.read",
    ],
    SystemRole.CONTENT_MANAGER.value: [
        "artists.read",
        "artists.write",
        "artists.approve",
        "tracks.read",
        "tracks.write",
        "tracks.publish",
        "tracks.takedown",
        "analytics.read",
    ],
    SystemRole.SUPPORT.value: [
        "users.read",
        "artists.read",
        "tracks.read",
        "payments.read",
        "security.read",
    ],
    SystemRole.ANALYST.value: [
        "analytics.read",
        "analytics.export",
        "artists.read",
        "tracks.read",
    ],
    SystemRole.FINANCE.value: [
        "payments.read",
        "payments.verify",
        "payments.refund",
        "royalties.read",
        "royalties.write",
        "analytics.read",
        "audit_logs.read",
    ],
    SystemRole.TECH_OPS.value: [
        "providers.read",
        "providers.configure",
        "providers.disable",
        "cache.read",
        "cache.purge",
        "jobs.read",
        "jobs.retry",
        "jobs.cancel",
        "settings.read",
        "feature_flags.read",
        "security.read",
        "audit_logs.read",
    ],
    SystemRole.ARTIST_MANAGER.value: [
        "artists.read",
        "artists.write",
        "artists.approve",
        "tracks.read",
        "tracks.write",
        "analytics.read",
    ],
}


class RbacService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_default_rbac(self) -> None:
        """Idempotently create default permissions and system roles."""
        # Permissions
        existing_perms = {
            p.code: p for p in (await self.session.execute(select(Permission))).scalars().all()
        }
        for code, desc in DEFAULT_PERMISSIONS.items():
            if code not in existing_perms:
                perm = Permission(code=code, description=desc)
                self.session.add(perm)
                existing_perms[code] = perm
        await self.session.flush()

        # Roles
        existing_roles = {
            r.name: r
            for r in (
                await self.session.execute(select(Role).options(selectinload(Role.permissions)))
            )
            .scalars()
            .all()
        }
        for role_name, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
            if role_name not in existing_roles:
                role = Role(
                    name=role_name,
                    description=f"System role: {role_name}",
                    is_system=True,
                )
                self.session.add(role)
                await self.session.flush()
                existing_roles[role_name] = role
                # A newly-created role has no loaded relationship yet. Do not
                # read role.permissions here: with AsyncSession that would
                # trigger an implicit lazy load and MissingGreenlet.
                current_codes: set[str] = set()
            else:
                role = existing_roles[role_name]
                current_codes = {p.code for p in (role.permissions or [])}
            for code in perm_codes:
                if code not in current_codes and code in existing_perms:
                    role.permissions.append(existing_perms[code])

        await self.session.flush()
        logger.info(
            "rbac_defaults_ensured", roles=len(existing_roles), permissions=len(existing_perms)
        )

    async def assign_role(
        self,
        user_id: UUID,
        role_name: str,
        granted_by: UUID | None = None,
    ) -> UserRole:
        role = await self.session.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            raise NotFoundError(f"Role '{role_name}' not found")

        existing = await self.session.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
            )
        )
        if existing is not None:
            raise ConflictError("User already has this role")

        user_role = UserRole(user_id=user_id, role_id=role.id, granted_by=granted_by)
        self.session.add(user_role)
        await self.session.flush()
        logger.info("role_assigned", user_id=str(user_id), role=role_name)
        return user_role

    async def revoke_role(self, user_id: UUID, role_name: str) -> None:
        role = await self.session.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            raise NotFoundError(f"Role '{role_name}' not found")

        user_role = await self.session.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
            )
        )
        if user_role is None:
            raise NotFoundError("User does not have this role")

        await self.session.delete(user_role)
        await self.session.flush()
        logger.info("role_revoked", user_id=str(user_id), role=role_name)

    async def get_user_roles(self, user_id: UUID) -> list[Role]:
        result = await self.session.execute(
            select(UserRole)
            .where(UserRole.user_id == user_id)
            .options(selectinload(UserRole.role).selectinload(Role.permissions))
        )
        return [ur.role for ur in result.scalars().all() if ur.role]

    async def user_has_permission(self, user_id: UUID, code: str) -> bool:
        roles = await self.get_user_roles(user_id)
        for role in roles:
            for perm in role.permissions or []:
                if perm.code == code:
                    return True
        return False
