"""Centralized authorization policy tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.artist_member import ArtistMemberRole
from app.services.authorization import AuthorizationService


@pytest.mark.asyncio
async def test_get_permission_codes_collects_permissions_from_all_roles() -> None:
    rows = [
        SimpleNamespace(
            role=SimpleNamespace(
                permissions=[
                    SimpleNamespace(code="tracks.read"),
                    SimpleNamespace(code="tracks.publish"),
                ]
            )
        ),
        SimpleNamespace(role=SimpleNamespace(permissions=[SimpleNamespace(code="users.read")])),
        SimpleNamespace(role=None),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    codes = await AuthorizationService(session).get_permission_codes(uuid4())

    assert codes == {"tracks.read", "tracks.publish", "users.read"}


@pytest.mark.asyncio
async def test_require_all_permissions_reports_missing_codes() -> None:
    service = AuthorizationService(SimpleNamespace())
    service.get_permission_codes = AsyncMock(return_value={"users.read"})

    with pytest.raises(ForbiddenError) as exc:
        await service.require_all_permissions(uuid4(), ["users.read", "users.suspend"])

    assert exc.value.details == {"missing": ["users.suspend"]}


@pytest.mark.asyncio
async def test_require_any_permission_accepts_one_matching_code() -> None:
    service = AuthorizationService(SimpleNamespace())
    service.get_permission_codes = AsyncMock(return_value={"artists.read"})

    await service.require_any_permission(uuid4(), ["artists.write", "artists.read"])


@pytest.mark.asyncio
async def test_require_artist_roles_accepts_active_artist_member() -> None:
    user_id = uuid4()
    artist_id = uuid4()
    artist = SimpleNamespace(status="active")
    member = SimpleNamespace(role=ArtistMemberRole.MANAGER)
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[artist, member]))

    result = await AuthorizationService(session).require_artist_roles(
        user_id,
        artist_id,
        {ArtistMemberRole.OWNER, ArtistMemberRole.MANAGER},
    )

    assert result is member
    assert session.scalar.await_count == 2


@pytest.mark.asyncio
async def test_require_artist_roles_hides_non_membership_as_not_found() -> None:
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[SimpleNamespace(status="active"), None]))

    with pytest.raises(NotFoundError):
        await AuthorizationService(session).require_artist_roles(
            uuid4(), uuid4(), {ArtistMemberRole.OWNER}
        )


@pytest.mark.asyncio
async def test_require_artist_roles_rejects_inactive_artist() -> None:
    session = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(status="suspended")))

    with pytest.raises(NotFoundError):
        await AuthorizationService(session).require_artist_roles(
            uuid4(), uuid4(), {ArtistMemberRole.OWNER}
        )

    assert session.scalar.await_count == 1


@pytest.mark.asyncio
async def test_artist_authorization_can_return_forbidden_for_upload_policy() -> None:
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[SimpleNamespace(status="active"), None]))

    with pytest.raises(ForbiddenError):
        await AuthorizationService(session).require_artist_roles(
            uuid4(),
            uuid4(),
            {ArtistMemberRole.OWNER, ArtistMemberRole.MANAGER, ArtistMemberRole.EDITOR},
            hide_existence=False,
        )
