"""Contract tests for MockProvider and ProviderManager."""

from __future__ import annotations

import pytest

from app.core.exceptions import (
    NotFoundError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    SourceExpiredError,
)
from app.providers.base import ProviderHealthStatus, SourceType
from app.providers.mock import MockProvider
from app.providers.registry import ProviderManager, create_default_registry


@pytest.fixture
def mock() -> MockProvider:
    return MockProvider()


@pytest.fixture
def manager() -> ProviderManager:
    return ProviderManager(create_default_registry(include_mock=True))


@pytest.mark.asyncio
async def test_mock_health(mock: MockProvider) -> None:
    health = await mock.health_check()
    assert health.status == ProviderHealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_mock_search(mock: MockProvider) -> None:
    results = await mock.search("chan")
    assert len(results) >= 1
    assert any("Chan" in t.title for t in results)


@pytest.mark.asyncio
async def test_mock_get_track(mock: MockProvider) -> None:
    track = await mock.get_track("mock-1")
    assert track is not None
    assert track.title == "Guantanamera"
    assert track.isrc == "QZMOCK000001"


@pytest.mark.asyncio
async def test_mock_get_not_found(mock: MockProvider) -> None:
    assert await mock.get_track("mock-not-found") is None


@pytest.mark.asyncio
async def test_mock_resolve(mock: MockProvider) -> None:
    source = await mock.resolve("mock-1", quality="medium")
    assert source is not None
    assert source.source_type == SourceType.SIGNED_URL
    assert source.url is not None
    assert "https://" in source.url
    assert source.supports_range is True


@pytest.mark.asyncio
async def test_mock_preview(mock: MockProvider) -> None:
    preview = await mock.preview("mock-1")
    assert preview is not None
    assert preview.duration_seconds == 30.0


@pytest.mark.asyncio
async def test_mock_resolve_errors(mock: MockProvider) -> None:
    with pytest.raises(NotFoundError):
        await mock.resolve("mock-not-found")
    with pytest.raises(ProviderRateLimitedError):
        await mock.resolve("mock-429")
    with pytest.raises(ProviderUnavailableError):
        await mock.resolve("mock-500")
    with pytest.raises(SourceExpiredError):
        await mock.resolve("mock-expired")


@pytest.mark.asyncio
async def test_manager_search(manager: ProviderManager) -> None:
    results = await manager.search("guantanamera")
    assert len(results) >= 1
    provider_name, meta = results[0]
    assert provider_name == "mock"
    assert "Guantanamera" in meta.title


@pytest.mark.asyncio
async def test_manager_health(manager: ProviderManager) -> None:
    health = await manager.health_all()
    assert "mock" in health
    assert health["mock"].status == ProviderHealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_manager_resolve(manager: ProviderManager) -> None:
    source = await manager.resolve("mock", "mock-2", quality="low")
    assert source is not None
    assert source.bitrate_kbps == 128


def test_capabilities(mock: MockProvider) -> None:
    caps = mock.capabilities
    assert caps.search is True
    assert caps.audio is True
    assert mock.is_available() is True
