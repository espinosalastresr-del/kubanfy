"""Browser and legacy login response contracts."""

from __future__ import annotations

from http.cookies import SimpleCookie
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from starlette.requests import Request

from app.api.v1 import auth
from app.core.config import Settings
from app.core.exceptions import AuthError
from pydantic import ValidationError

from app.schemas.auth import BrowserLoginResponse, LoginRequest, LoginResponse, TokenResponse, UserResponse


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


WEB_ORIGIN = "https://kubanfy-web-staging.globumlatinmusic.workers.dev"


def make_login_request(origin: str | None) -> Request:
    headers = [(b"user-agent", b"pytest")]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/v1/auth/login",
        "raw_path": b"/v1/auth/login",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 443),
    })


def install_login_mocks(monkeypatch: pytest.MonkeyPatch):
    user = UserResponse.model_validate({
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
    })
    tokens = TokenResponse(
        access_token="access-value",
        refresh_token="refresh-value",
        expires_in=1800,
    )
    service = SimpleNamespace(login=AsyncMock(return_value=(user, tokens)))
    anti_abuse = SimpleNamespace(check_login=AsyncMock())
    geo = SimpleNamespace(
        resolve_client_ip=lambda ip, **_kwargs: ip,
        resolve=lambda _ip: SimpleNamespace(country="CU"),
    )

    class FakeAuthService:
        def __new__(cls, _session):
            return service

        @staticmethod
        def to_response(value):
            return value

    monkeypatch.setattr(auth, "AuthService", FakeAuthService)
    monkeypatch.setattr(auth, "AntiAbuseService", lambda: anti_abuse)
    monkeypatch.setattr(auth, "GeoService", lambda: geo)
    return service, anti_abuse


@pytest.mark.asyncio
async def test_allowed_browser_login_sets_cookie_and_hides_refresh_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, anti_abuse = install_login_mocks(monkeypatch)
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: Settings(environment="staging", cors_origins=WEB_ORIGIN),
    )
    response = Response()

    result = await auth.login(
        body=LoginRequest(email="listener@example.com", password="password"),
        request=make_login_request(WEB_ORIGIN),
        response=response,
        session=object(),
    )

    assert isinstance(result, BrowserLoginResponse)
    assert result.tokens.access_token == "access-value"
    assert not hasattr(result.tokens, "refresh_token")
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    assert cookie["kubanfy_refresh"]["httponly"]
    assert cookie["kubanfy_refresh"]["secure"]
    assert cookie["kubanfy_refresh"]["path"] == "/api/v1/auth"
    service.login.assert_awaited_once()
    anti_abuse.check_login.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_login_without_origin_keeps_json_refresh_token_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, anti_abuse = install_login_mocks(monkeypatch)
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: pytest.fail("legacy login must not load browser origin settings"),
    )
    response = Response()

    result = await auth.login(
        body=LoginRequest(email="listener@example.com", password="password"),
        request=make_login_request(None),
        response=response,
        session=object(),
    )

    assert isinstance(result, LoginResponse)
    assert result.tokens.refresh_token == "refresh-value"
    assert "set-cookie" not in response.headers
    service.login.assert_awaited_once()
    anti_abuse.check_login.assert_awaited_once()
