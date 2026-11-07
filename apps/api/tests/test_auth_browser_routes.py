"""Browser refresh and logout endpoint contracts."""

from __future__ import annotations

from http.cookies import SimpleCookie
from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from starlette.requests import Request

from app.api.v1 import auth
from app.core.config import Settings
from app.core.exceptions import AuthError
from app.schemas.auth import RefreshRequest, TokenResponse

WEB_ORIGIN = "https://kubanfy-web-staging.globumlatinmusic.workers.dev"
REFRESH_VALUE = "signed-refresh-cookie"


def make_request(*, origin: str | None, cookie: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    if cookie is not None:
        headers.append((b"cookie", cookie.encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/api/v1/auth/refresh",
            "raw_path": b"/api/v1/auth/refresh",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 443),
        }
    )


def settings() -> Settings:
    return Settings(environment="staging", cors_origins=WEB_ORIGIN)


def issued_tokens() -> TokenResponse:
    return TokenResponse(
        access_token="new-access",
        refresh_token="new-refresh",
        expires_in=1800,
    )


@pytest.mark.asyncio
async def test_browser_refresh_reads_cookie_rotates_it_and_hides_refresh_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = type("Service", (), {"refresh": AsyncMock(return_value=issued_tokens())})()
    monkeypatch.setattr(auth, "AuthService", lambda _session: service)
    monkeypatch.setattr(auth, "get_settings", settings)
    response = Response()

    result = await auth.refresh(
        body=None,
        request=make_request(
            origin=WEB_ORIGIN,
            cookie=f"kubanfy_refresh={REFRESH_VALUE}",
        ),
        response=response,
        session=object(),
    )

    assert result.access_token == "new-access"
    assert not hasattr(result, "refresh_token")
    service.refresh.assert_awaited_once_with(REFRESH_VALUE, device_id=None)
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    morsel = cookie["kubanfy_refresh"]
    assert morsel.value == "new-refresh"
    assert morsel["httponly"]
    assert morsel["secure"]
    assert morsel["samesite"].lower() == "lax"
    assert morsel["path"] == "/api/v1/auth"
    assert morsel["domain"] == ""


@pytest.mark.asyncio
async def test_legacy_refresh_keeps_json_body_and_response_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = type("Service", (), {"refresh": AsyncMock(return_value=issued_tokens())})()
    monkeypatch.setattr(auth, "AuthService", lambda _session: service)
    response = Response()

    result = await auth.refresh(
        body=RefreshRequest(refresh_token="legacy-refresh", device_id="native-1"),
        request=make_request(origin=None),
        response=response,
        session=object(),
    )

    assert result.refresh_token == "new-refresh"
    service.refresh.assert_awaited_once_with("legacy-refresh", device_id="native-1")
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_browser_refresh_rejects_untrusted_origin_before_rotating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = type("Service", (), {"refresh": AsyncMock(return_value=issued_tokens())})()
    monkeypatch.setattr(auth, "AuthService", lambda _session: service)
    monkeypatch.setattr(auth, "get_settings", settings)

    with pytest.raises(AuthError):
        await auth.refresh(
            body=None,
            request=make_request(
                origin="https://evil.example",
                cookie=f"kubanfy_refresh={REFRESH_VALUE}",
            ),
            response=Response(),
            session=object(),
        )

    service.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_browser_refresh_rejects_missing_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = type("Service", (), {"refresh": AsyncMock(return_value=issued_tokens())})()
    monkeypatch.setattr(auth, "AuthService", lambda _session: service)
    monkeypatch.setattr(auth, "get_settings", settings)

    with pytest.raises(AuthError):
        await auth.refresh(
            body=None,
            request=make_request(origin=WEB_ORIGIN),
            response=Response(),
            session=object(),
        )

    service.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_browser_logout_revokes_cookie_session_and_expires_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = type("Service", (), {"logout": AsyncMock(return_value=None)})()
    monkeypatch.setattr(auth, "AuthService", lambda _session: service)
    monkeypatch.setattr(auth, "get_settings", settings)
    response = Response()

    await auth.logout(
        request=make_request(
            origin=WEB_ORIGIN,
            cookie=f"kubanfy_refresh={REFRESH_VALUE}",
        ),
        response=response,
        session=object(),
    )

    service.logout.assert_awaited_once_with(REFRESH_VALUE)
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    morsel = cookie["kubanfy_refresh"]
    assert morsel.value == ""
    assert morsel["max-age"] == "0"
    assert morsel["path"] == "/api/v1/auth"
