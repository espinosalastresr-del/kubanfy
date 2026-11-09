"""Release assignment invariants for first-party artist audio uploads."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.music import ReleaseType, TrackStatus
from app.services.artist_upload import ArtistUploadService


def service_for(session):
    service = object.__new__(ArtistUploadService)
    service.session = session
    return service


@pytest.mark.asyncio
async def test_upload_can_attach_track_to_owned_draft_album() -> None:
    artist_id = uuid4()
    release_id = uuid4()
    release = SimpleNamespace(
        id=release_id,
        artist_id=artist_id,
        type=ReleaseType.ALBUM,
        status=TrackStatus.DRAFT,
    )
    session = SimpleNamespace(
        get=AsyncMock(return_value=release),
        scalar=AsyncMock(return_value=None),
        add=Mock(),
        flush=AsyncMock(),
    )

    result = await service_for(session)._resolve_upload_release(
        artist_id=artist_id,
        title="Track title",
        release_id=release_id,
    )

    assert result is release
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_upload_rejects_release_owned_by_another_artist() -> None:
    session = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(
            id=uuid4(),
            artist_id=uuid4(),
            type=ReleaseType.ALBUM,
            status=TrackStatus.DRAFT,
        )),
        scalar=AsyncMock(return_value=None),
        add=Mock(),
        flush=AsyncMock(),
    )

    with pytest.raises(NotFoundError, match="Release not found"):
        await service_for(session)._resolve_upload_release(
            artist_id=uuid4(),
            title="Track title",
            release_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_upload_rejects_non_draft_release() -> None:
    artist_id = uuid4()
    release_id = uuid4()
    session = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(
            id=release_id,
            artist_id=artist_id,
            type=ReleaseType.ALBUM,
            status=TrackStatus.PUBLISHED,
        )),
        scalar=AsyncMock(return_value=None),
        add=Mock(),
        flush=AsyncMock(),
    )

    with pytest.raises(ValidationError, match="draft release"):
        await service_for(session)._resolve_upload_release(
            artist_id=artist_id,
            title="Track title",
            release_id=release_id,
        )


@pytest.mark.asyncio
async def test_single_release_cannot_receive_a_second_track() -> None:
    artist_id = uuid4()
    release_id = uuid4()
    release = SimpleNamespace(
        id=release_id,
        artist_id=artist_id,
        type=ReleaseType.SINGLE,
        status=TrackStatus.DRAFT,
    )
    session = SimpleNamespace(
        get=AsyncMock(return_value=release),
        scalar=AsyncMock(return_value=uuid4()),
        add=Mock(),
        flush=AsyncMock(),
    )

    with pytest.raises(ValidationError, match="only one track"):
        await service_for(session)._resolve_upload_release(
            artist_id=artist_id,
            title="Track title",
            release_id=release_id,
        )


@pytest.mark.asyncio
async def test_upload_without_release_creates_a_single_release() -> None:
    artist_id = uuid4()
    added = []
    session = SimpleNamespace(
        get=AsyncMock(),
        scalar=AsyncMock(),
        add=Mock(side_effect=added.append),
        flush=AsyncMock(),
    )

    release = await service_for(session)._resolve_upload_release(
        artist_id=artist_id,
        title="  New single  ",
        release_id=None,
    )

    assert release in added
    assert release.artist_id == artist_id
    assert release.title == "New single"
    assert release.type == ReleaseType.SINGLE
    assert release.status == TrackStatus.DRAFT
    session.flush.assert_awaited_once()
