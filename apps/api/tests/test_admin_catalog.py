"""Regression coverage for the RBAC-protected admin catalog surface."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.api.v1.admin import CatalogTrackStatus, _catalog_slug
from app.models.rbac import SystemRole
from app.services.rbac import DEFAULT_ROLE_PERMISSIONS


def test_catalog_slug_normalizes_accents_and_punctuation() -> None:
    assert _catalog_slug("Bárbara & Los Niños!") == "barbara-los-ninos"


def test_catalog_manager_roles_have_all_required_permissions() -> None:
    required = {
        "tracks.read",
        "tracks.write",
        "tracks.publish",
        "tracks.takedown",
        "artists.write",
    }
    for role in (SystemRole.SUPER_ADMIN, SystemRole.ADMIN, SystemRole.CONTENT_MANAGER):
        assert required.issubset(set(DEFAULT_ROLE_PERMISSIONS[role.value]))


def test_catalog_status_does_not_allow_publish_bypass() -> None:
    assert CatalogTrackStatus(status="hidden").status == "hidden"
    with pytest.raises(PydanticValidationError):
        CatalogTrackStatus(status="published")
