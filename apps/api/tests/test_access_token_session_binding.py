"""Access-token/session binding and immediate revocation tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import AuthError
from app.core.security import create_access_token, decode_token
from app.models.device import SessionStatus
from app.models.user import UserStatus


def make_auth_context(*, session_status: SessionStatus = SessionStatus.ACTIVE):
    user_id = uuid4()
    settings = get_settings()
    token = create_access_token(str(user_id), settings=settings)
    jti = decode_token(token, settings)["jti"]
    now = datetime.now(UTC)
    user = SimpleNamespace(
        id=user_id,
        status=UserStatus.ACTIVE,
        email_verified=True,
    )
    auth_session = SimpleNamespace(
        access_token_jti=jti,
        device_id=None,
        status=session_status,
        expires_at=now + timedelta(days=7),
        last_activity_at=now,
    )
    credentials = SimpleNamespace(credentials=token, scheme="Bearer")
    db = SimpleNamespace(
        get=AsyncMock(return_value=user),
        scalar=AsyncMock(return_value=auth_session),
    )
    return credentials, db, auth_session, jti


@pytest.mark.asyncio
async def test_access_token_requires_a_persisted_active_session() -> None:
    credentials, db, _, _ = make_auth_context()

    user = await get_current_user(credentials, db)

    assert user.email_verified is True
    db.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoked_session_invalidates_existing_access_token() -> None:
    credentials, db, _, _ = make_auth_context(
        session_status=SessionStatus.REVOKED
    )

    with pytest.raises(AuthError) as error:
        await get_current_user(credentials, db)

    assert error.value.code == "SESSION_INVALID"
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_access_token_without_session_binding_is_rejected() -> None:
    credentials, db, _, _ = make_auth_context()
    db.scalar = AsyncMock(return_value=None)

    with pytest.raises(AuthError) as error:
        await get_current_user(credentials, db)

    assert error.value.code == "SESSION_INVALID"


@pytest.mark.asyncio
async def test_expired_session_rejects_access_token() -> None:
    credentials, db, auth_session, _ = make_auth_context()
    auth_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    with pytest.raises(AuthError) as error:
        await get_current_user(credentials, db)

    assert error.value.code == "SESSION_EXPIRED"


@pytest.mark.asyncio
async def test_idle_session_rejects_access_token() -> None:
    credentials, db, auth_session, _ = make_auth_context()
    auth_session.last_activity_at = datetime.now(UTC) - timedelta(
        minutes=get_settings().session_idle_timeout_minutes + 1
    )

    with pytest.raises(AuthError) as error:
        await get_current_user(credentials, db)

    assert error.value.code == "SESSION_EXPIRED"
