"""Authentication must not issue or refresh tokens for unverified email addresses."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import AuthError
from app.models.user import UserStatus
from app.schemas.auth import LoginRequest
from app.services.auth import AuthService


@pytest.mark.asyncio
async def test_login_rejects_unverified_user_before_creating_session(monkeypatch):
    user = SimpleNamespace(
        id=uuid4(),
        email="legacy@example.com",
        password_hash="stored-hash",
        email_verified=False,
        status=UserStatus.ACTIVE,
        last_login_at=None,
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=user)
    session.flush = AsyncMock()
    settings = Settings(
        environment="test",
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
    )
    monkeypatch.setattr("app.services.auth.verify_password", lambda *_args: True)
    service = AuthService(session, settings)

    with pytest.raises(AuthError) as error:
        await service.login(LoginRequest(email=user.email, password="Correct123!"))

    assert error.value.code == "EMAIL_NOT_VERIFIED"
    assert error.value.status_code == 403
    session.flush.assert_not_awaited()
