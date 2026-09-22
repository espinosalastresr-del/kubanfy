"""Unit tests for RBAC default catalog consistency."""

from __future__ import annotations

from app.models.rbac import SystemRole
from app.services.rbac import DEFAULT_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS


def test_all_system_roles_have_permissions() -> None:
    for role in SystemRole:
        assert role.value in DEFAULT_ROLE_PERMISSIONS, f"Missing role {role.value}"
        assert len(DEFAULT_ROLE_PERMISSIONS[role.value]) > 0


def test_super_admin_has_all_permissions() -> None:
    super_perms = set(DEFAULT_ROLE_PERMISSIONS[SystemRole.SUPER_ADMIN.value])
    assert super_perms == set(DEFAULT_PERMISSIONS.keys())


def test_permission_codes_are_unique_and_well_formed() -> None:
    codes = list(DEFAULT_PERMISSIONS.keys())
    assert len(codes) == len(set(codes))
    for code in codes:
        assert "." in code, f"Permission code should be resource.action: {code}"
        resource, action = code.split(".", 1)
        assert resource and action


def test_role_permissions_reference_known_codes() -> None:
    known = set(DEFAULT_PERMISSIONS.keys())
    for role_name, codes in DEFAULT_ROLE_PERMISSIONS.items():
        for code in codes:
            assert code in known, f"Role {role_name} references unknown permission {code}"
