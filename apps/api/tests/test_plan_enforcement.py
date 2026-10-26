"""Regression tests for plan enforcement and editable profile validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import EntitlementRequiredError
from app.models.entitlement import EntitlementScope
from app.schemas.auth import ProfileUpdateRequest
from app.services.entitlement import EntitlementService


def entitlement(scope: EntitlementScope, metadata: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        scope_type=scope,
        metadata_json=metadata or {},
        status="active",
        starts_at=datetime.now(UTC) - timedelta(minutes=1),
        expires_at=None,
    )


@pytest.mark.asyncio
async def test_download_access_requires_explicit_download_feature(monkeypatch) -> None:
    service = EntitlementService(None)  # type: ignore[arg-type]
    active = [entitlement(EntitlementScope.USER_PREMIUM, {"plan_code": "premium", "downloads": False})]

    async def list_active(_user_id):
        return active

    monkeypatch.setattr(service, "list_active", list_active)
    with pytest.raises(EntitlementRequiredError):
        await service.require_download_access(uuid4())

    active[0].metadata_json["downloads"] = True
    await service.require_download_access(uuid4())


@pytest.mark.asyncio
async def test_track_entitlement_does_not_grant_downloads(monkeypatch) -> None:
    service = EntitlementService(None)  # type: ignore[arg-type]

    async def list_active(_user_id):
        return [entitlement(EntitlementScope.TRACK, {"downloads": True})]

    monkeypatch.setattr(service, "list_active", list_active)
    with pytest.raises(EntitlementRequiredError):
        await service.require_download_access(uuid4())


@pytest.mark.asyncio
async def test_quality_limit_is_enforced_from_effective_plan(monkeypatch) -> None:
    service = EntitlementService(None)  # type: ignore[arg-type]
    active = [entitlement(EntitlementScope.USER_PREMIUM, {"quality_max": "medium"})]

    async def list_active(_user_id):
        return active

    monkeypatch.setattr(service, "list_active", list_active)
    user_id = uuid4()
    await service.require_quality_access(user_id, "low")
    await service.require_quality_access(user_id, "medium")
    with pytest.raises(EntitlementRequiredError):
        await service.require_quality_access(user_id, "lossless")
    with pytest.raises(EntitlementRequiredError):
        await service.require_quality_access(user_id, "unknown")

    active[0].metadata_json["quality_max"] = "lossless"
    await service.require_quality_access(user_id, "lossless")


def test_profile_update_normalizes_supported_fields() -> None:
    body = ProfileUpdateRequest(display_name="  Ray  ", country="cu", language="ES")
    assert body.display_name == "Ray"
    assert body.country == "CU"
    assert body.language == "es"


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": "   ", "country": "CU", "language": "es"},
        {"display_name": "Name", "country": "C1", "language": "es"},
        {"display_name": "Name", "country": "CUB", "language": "es"},
        {"display_name": "Name", "country": "CU", "language": "fr"},
    ],
)
def test_profile_update_rejects_invalid_values(payload: dict) -> None:
    with pytest.raises(ValueError):
        ProfileUpdateRequest(**payload)
