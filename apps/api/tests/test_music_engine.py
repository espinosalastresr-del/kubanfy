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


@pytest.mark.asyncio
async def test_catalog_playback_uses_existing_kby2_derivative() -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from app.models.music import AudioQuality, SourceType, TrackStatus
    from app.services.music_engine import MusicEngine
    from app.storage import StorageBucket

    track_id = uuid4()
    track = SimpleNamespace(id=track_id, status=TrackStatus.PUBLISHED, duration=12.0)
    asset = SimpleNamespace(
        track_id=track_id,
        quality=AudioQuality.LOW,
        source_type=SourceType.DERIVATIVE,
        storage_key="artists/demo/tracks/demo/low/audio.kby",
        content_hash="a" * 64,
        duration=12.0,
        codec="aac",
        version=1,
    )

    class Session:
        async def get(self, model, identifier):
            return track

        async def scalar(self, statement):
            return asset

    class Storage:
        async def exists(self, key, *, bucket):
            assert key == "artists/demo/tracks/demo/low/audio.kby2"
            assert bucket == StorageBucket.PERMANENT
            return True

        async def signed_url(self, key, *, bucket):
            assert key.endswith(".kby2")
            return SimpleNamespace(url="https://storage.example/audio.kby2", expires_in_seconds=300)

    engine = MusicEngine.__new__(MusicEngine)
    engine.session = Session()
    engine.storage = Storage()

    result = await engine.download_by_track_id(
        track_id=track_id,
        quality="low",
        kby_version=2,
    )
    assert result.kby_version == 2
    assert result.storage_key.endswith(".kby2")
    assert result.signed_url.url.endswith(".kby2")


@pytest.mark.asyncio
async def test_catalog_playback_rejects_missing_kby2_derivative() -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from app.core.exceptions import NotFoundError
    from app.models.music import AudioQuality, SourceType, TrackStatus
    from app.services.music_engine import MusicEngine

    track_id = uuid4()
    track = SimpleNamespace(id=track_id, status=TrackStatus.PUBLISHED, duration=12.0)
    asset = SimpleNamespace(
        track_id=track_id,
        quality=AudioQuality.LOW,
        source_type=SourceType.DERIVATIVE,
        storage_key="artists/demo/tracks/demo/low/audio.kby",
        content_hash="b" * 64,
        duration=12.0,
        codec="aac",
        version=1,
    )

    class Session:
        async def get(self, model, identifier):
            return track

        async def scalar(self, statement):
            return asset

    class Storage:
        async def exists(self, key, *, bucket):
            return False

    engine = MusicEngine.__new__(MusicEngine)
    engine.session = Session()
    engine.storage = Storage()

    with pytest.raises(NotFoundError, match="KBY v2 streaming asset is not available"):
        await engine.download_by_track_id(
            track_id=track_id,
            quality="low",
            kby_version=2,
        )
