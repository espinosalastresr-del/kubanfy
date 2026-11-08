"""Browser and legacy login response contracts."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from starlette.requests import Request

from app.api.v1 import auth
from app.core.config import Settings
from app.core.exceptions import AuthError
from pydantic import ValidationError

from app.schemas.auth import BrowserLoginResponse, LoginRequest, LoginResponse


def test_browser_login_response_never_accepts_or_serializes_refresh_token() -> None:
    payload = {
        "user": {
            "id": "6d2d6e8a-6c1a-4a9a-8a1a-7b9d8f1a2c33",
            "email": "listener@example.com",
            "display_name": "Listener",
            "avatar": None,
            "country": "CU",
            "language": "es",
            "status": "active",
            "email_verified": True,
            "created_at": "2026-01-01T00:00:00Z",
            "last_login_at": None,
        },
        "tokens": {
            "access_token": "access-value",
            "token_type": "bearer",
            "expires_in": 1800,
        },
    }

    response = BrowserLoginResponse.model_validate(payload)
    serialized = response.model_dump()

    assert serialized["tokens"]["access_token"] == "access-value"
    assert "refresh_token" not in serialized["tokens"]


def test_legacy_login_response_keeps_refresh_token_contract() -> None:
    assert "refresh_token" in LoginResponse.model_fields["tokens"].annotation.model_fields


def test_browser_login_response_rejects_missing_access_token() -> None:
    payload = {
        "user": {
            "id": "6d2d6e8a-6c1a-4a9a-8a1a-7b9d8f1a2c33",
            "email": "listener@example.com",
            "display_name": "Listener",
            "avatar": None,
            "country": "CU",
            "language": "es",
            "status": "active",
            "email_verified": True,
            "created_at": "2026-01-01T00:00:00Z",
            "last_login_at": None,
        },
        "tokens": {"token_type": "bearer", "expires_in": 1800},
    }

    with pytest.raises(ValidationError):
        BrowserLoginResponse.model_validate(payload)


@pytest.mark.asyncio
async def test_login_rejects_untrusted_origin_before_any_authentication_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web_origin = "https://kubanfy-web-staging.globumlatinmusic.workers.dev"
    anti_abuse = SimpleNamespace(check_login=AsyncMock())
    auth_service = SimpleNamespace(login=AsyncMock())
    geo = SimpleNamespace(
        resolve_client_ip=lambda ip, _forwarded_for=None: ip,
        resolve=lambda _ip: SimpleNamespace(country="US"),
    )
    monkeypatch.setattr(auth, "get_settings", lambda: Settings(
        environment="staging",
        cors_origins=web_origin,
    ))
    monkeypatch.setattr(auth, "AntiAbuseService", lambda: anti_abuse)
    monkeypatch.setattr(auth, "AuthService", lambda _session: auth_service)
    monkeypatch.setattr(auth, "GeoService", lambda: geo)

    request = Request({
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/v1/auth/login",
        "raw_path": b"/v1/auth/login",
        "query_string": b"",
        "headers": [(b"origin", b"https://evil.example")],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 443),
    })

    with pytest.raises(AuthError):
        await auth.login(
            body=LoginRequest(email="listener@example.com", password="password"),
            request=request,
            response=Response(),
            session=object(),
        )

    anti_abuse.check_login.assert_not_awaited()
    auth_service.login.assert_not_awaited()
