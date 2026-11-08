"""Authentication endpoint rate-limit regression tests."""
from __future__ import annotations

import hashlib

import pytest
from starlette.requests import Request

from app.api.v1 import auth
from app.schemas.auth import PasswordResetRequest


@pytest.mark.asyncio
async def test_password_reset_request_limits_by_ip_and_normalized_email(monkeypatch) -> None:
    calls: list[tuple[str, int, int]] = []
    requested_emails: list[str] = []

    class FakeLimiter:
        async def enforce_rate_limit(
            self, key: str, *, limit: int, window_seconds: int
        ) -> None:
            calls.append((key, limit, window_seconds))

    class FakePasswordResetService:
        def __init__(self, session) -> None:
            assert session is sentinel_session

        async def request_reset(self, email: str) -> None:
            requested_emails.append(email)

    sentinel_session = object()
    monkeypatch.setattr(auth, "_resolve_request_ip", lambda request: "203.0.113.10")
    monkeypatch.setattr(auth, "AntiAbuseService", FakeLimiter)
    monkeypatch.setattr(auth, "PasswordResetService", FakePasswordResetService)

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/v1/auth/password-reset/request",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
        }
    )
    body = PasswordResetRequest(email="Person@example.com")

    result = await auth.request_password_reset(body, request, sentinel_session)

    email_key = hashlib.sha256(b"person@example.com").hexdigest()
    assert calls == [
        ("password-reset:ip:203.0.113.10", 5, 900),
        (f"password-reset:email:{email_key}", 3, 900),
    ]
    assert requested_emails == ["Person@example.com"]
    assert result["message"].startswith("Si existe una cuenta")
