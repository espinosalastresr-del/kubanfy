"""Regression tests for effective entitlement dates."""

from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.entitlement import EntitlementScope, EntitlementStatus
from app.services.entitlement import EntitlementService


class _Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _Result:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return _Scalars(self.values)


@pytest.mark.asyncio
async def test_list_active_excludes_future_entitlements_without_expiring_them():
    now = datetime.now(UTC)
    future = SimpleNamespace(
        starts_at=now + timedelta(days=1), expires_at=None,
        status=EntitlementStatus.ACTIVE, scope_type=EntitlementScope.USER_PREMIUM,
        metadata_json={"downloads": True},
    )
    session = SimpleNamespace(execute=AsyncMock(return_value=_Result([future])), flush=AsyncMock())

    active = await EntitlementService(session).list_active(uuid4())

    assert active == []
    assert future.status == EntitlementStatus.ACTIVE
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_active_normalizes_offsets_and_naive_database_timestamps():
    now = datetime.now(UTC)
    expired = SimpleNamespace(
        starts_at=(now - timedelta(days=2)).astimezone(timezone(timedelta(hours=5))),
        expires_at=(now - timedelta(minutes=1)).astimezone(timezone(timedelta(hours=5))),
        status=EntitlementStatus.ACTIVE, scope_type=EntitlementScope.USER_PREMIUM,
        metadata_json={"downloads": True},
    )
    current = SimpleNamespace(
        starts_at=(now - timedelta(days=1)).replace(tzinfo=None),
        expires_at=(now + timedelta(days=1)).replace(tzinfo=None),
        status=EntitlementStatus.ACTIVE, scope_type=EntitlementScope.USER_PREMIUM,
        metadata_json={"downloads": True},
    )
    session = SimpleNamespace(execute=AsyncMock(return_value=_Result([expired, current])), flush=AsyncMock())

    active = await EntitlementService(session).list_active(uuid4())

    assert active == [current]
    assert expired.status == EntitlementStatus.EXPIRED
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_free_entitlement_allows_low_streaming_but_blocks_downloads_and_higher_quality():
    from app.core.exceptions import EntitlementRequiredError

    service = EntitlementService(SimpleNamespace())
    service.list_active = AsyncMock(return_value=[])

    await service.require_quality_access(uuid4(), "low")
    with pytest.raises(EntitlementRequiredError):
        await service.require_quality_access(uuid4(), "medium")
    with pytest.raises(EntitlementRequiredError):
        await service.require_download_access(uuid4())


@pytest.mark.asyncio
async def test_premium_features_allow_downloads_and_medium_but_not_lossless():
    from app.core.exceptions import EntitlementRequiredError

    premium = SimpleNamespace(
        scope_type=EntitlementScope.USER_PREMIUM,
        metadata_json={"downloads": True, "quality_max": "medium", "plan_code": "premium"},
    )
    service = EntitlementService(SimpleNamespace())
    service.list_active = AsyncMock(return_value=[premium])

    await service.require_download_access(uuid4())
    await service.require_quality_access(uuid4(), "medium")
    with pytest.raises(EntitlementRequiredError):
        await service.require_quality_access(uuid4(), "lossless")
