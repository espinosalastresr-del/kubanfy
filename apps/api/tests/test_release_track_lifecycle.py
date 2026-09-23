"""Regression tests for terminal catalog lifecycle states."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ValidationError
from app.models.artist_member import ArtistMemberRole
from app.models.music import TrackStatus
from app.services.release_track import ReleaseTrackService


@pytest.mark.asyncio
async def test_deleted_release_cannot_change_status() -> None:
    artist_id = uuid4()
    release_id = uuid4()
    user_id = uuid4()
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=SimpleNamespace(role=ArtistMemberRole.OWNER)),
        get=AsyncMock(
            return_value=SimpleNamespace(
                artist_id=artist_id,
                status=TrackStatus.DELETED,
            )
        ),
    )

    service = ReleaseTrackService(session)
    with pytest.raises(ValidationError, match="Deleted release cannot change status"):
        await service.set_release_status(
            user_id=user_id,
            artist_id=artist_id,
            release_id=release_id,
            status=TrackStatus.HIDDEN,
        )


@pytest.mark.asyncio
async def test_deleted_track_cannot_change_status() -> None:
    artist_id = uuid4()
    track_id = uuid4()
    user_id = uuid4()
    session = SimpleNamespace(
        scalar=AsyncMock(
            side_effect=[
                SimpleNamespace(role=ArtistMemberRole.OWNER),
                SimpleNamespace(),
            ]
        ),
        get=AsyncMock(
            return_value=SimpleNamespace(
                status=TrackStatus.DELETED,
                release_id=uuid4(),
            )
        ),
    )

    service = ReleaseTrackService(session)
    with pytest.raises(ValidationError, match="Deleted track cannot change status"):
        await service.set_track_status(
            user_id=user_id,
            artist_id=artist_id,
            track_id=track_id,
            status=TrackStatus.DRAFT,
        )


def test_terminal_status_values_are_stable() -> None:
    assert TrackStatus.DELETED.value == "deleted"
    assert TrackStatus.TAKEDOWN.value == "takedown"
    assert TrackStatus.HIDDEN.value == "hidden"
