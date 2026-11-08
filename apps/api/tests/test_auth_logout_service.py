"""Session-scoped browser logout service tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.config import Settings
from app.models.device import SessionStatus
from app.services import auth as auth_service_module
from app.services.auth import AuthService


def make_service(session_row):
    database = SimpleNamespace(flush=AsyncMock())
    lookup = AsyncMock(return_value=session_row)
    service = AuthService.__new__(AuthService)
    service.settings = Settings()
    service.session = database
    service.sessions = SimpleNamespace(get_session_by_jti=lookup)
    return service, database, lookup


@pytest.mark.asyncio
async def test_logout_revokes_only_the_session_identified_by_refresh_jti(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_session = SimpleNamespace(
        status=SessionStatus.ACTIVE,
        revoked_at=None,
        user_id=UUID("6d2d6e8a-6c1a-4a9a-8a1a-7b9d8f1a2c33"),
    )
    service, database, lookup = make_service(active_session)
    monkeypatch.setattr(
        auth_service_module,
        "decode_token",
        lambda _token, _settings: {"type": "refresh", "jti": "current-session-jti"},
    )

    await service.logout("signed-refresh-token")

    assert active_session.status == SessionStatus.REVOKED
    assert active_session.revoked_at is not None
    lookup.assert_awaited_once_with("current-session-jti", for_update=True)
    database.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_is_idempotent_for_already_revoked_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revoked_session = SimpleNamespace(
        status=SessionStatus.REVOKED,
        revoked_at=None,
        user_id=UUID("6d2d6e8a-6c1a-4a9a-8a1a-7b9d8f1a2c33"),
    )
    service, database, lookup = make_service(revoked_session)
    monkeypatch.setattr(
        auth_service_module,
        "decode_token",
        lambda _token, _settings: {"type": "refresh", "jti": "already-revoked-jti"},
    )

    await service.logout("signed-refresh-token")

    lookup.assert_awaited_once_with("already-revoked-jti", for_update=True)
    database.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_does_not_lookup_a_session_for_malformed_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, database, lookup = make_service(None)

    def reject_token(_token, _settings):
        raise ValueError("invalid token")

    monkeypatch.setattr(auth_service_module, "decode_token", reject_token)

    await service.logout("malformed-token")

    lookup.assert_not_awaited()
    database.flush.assert_not_awaited()
