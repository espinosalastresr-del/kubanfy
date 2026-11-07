"""Contract tests for browser refresh-cookie attributes."""

from __future__ import annotations

from fastapi import Response

from app.core.auth_cookies import clear_refresh_cookie, set_refresh_cookie
from app.core.config import Settings


def test_set_refresh_cookie_is_host_only_http_only_and_scoped_to_auth() -> None:
    response = Response()
    settings = Settings(
        environment="staging",
        refresh_token_expire_days=30,
    )

    set_refresh_cookie(response, "refresh-secret", settings)
    cookie = response.headers["set-cookie"]

    assert cookie.startswith("kubanfy_refresh=refresh-secret")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api/v1/auth" in cookie
    assert "Max-Age=2592000" in cookie
    assert "Domain=" not in cookie


def test_clear_refresh_cookie_uses_the_same_scope_and_expires_it() -> None:
    response = Response()

    clear_refresh_cookie(response)
    cookie = response.headers["set-cookie"]

    assert cookie.startswith("kubanfy_refresh=")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api/v1/auth" in cookie
    assert "Max-Age=0" in cookie
    assert "Domain=" not in cookie
