"""Unit tests for MusicEngine helpers and provider-backed preview."""

from __future__ import annotations

import pytest

from app.providers.registry import ProviderManager, create_default_registry
from app.services.music_engine import _slugify


def test_slugify() -> None:
    assert _slugify("Guantanamera!") == "guantanamera"
    assert _slugify("Dos  Gardenias") == "dos-gardenias"
    assert _slugify("Ñoño & Co.") == "nono-co"
    assert len(_slugify("a" * 300)) <= 200


@pytest.mark.asyncio
async def test_engine_preview_via_manager() -> None:
    """Preview does not require DB — exercise provider path."""
    manager = ProviderManager(create_default_registry(include_mock=True))
    source = await manager.preview("mock", "mock-1")
    assert source is not None
    assert source.url is not None
    assert source.duration_seconds == 30.0


@pytest.mark.asyncio
async def test_engine_resolve_via_manager() -> None:
    manager = ProviderManager(create_default_registry(include_mock=True))
    source = await manager.resolve("mock", "mock-1", quality="lossless")
    assert source is not None
    assert source.codec == "flac"
    assert source.bitrate_kbps == 1411
