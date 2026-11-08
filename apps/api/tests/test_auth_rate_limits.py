"""Authentication endpoint rate-limit regression tests."""
from __future__ import annotations

import hashlib

import pytest
from starlette.requests import Request

from app.api.v1 import auth
from app.core.exceptions import RateLimitError
from app.schemas.auth import PasswordResetRequest


@pytest.mark.asyncio
async def test_password_reset_request_limits_by_ip_and_normalized_email(monkeypatch) -> None:
    calls: list[tuple[str, int, int]] = []
    counts: dict[str, int] = {}
    requested_emails: list[str] = []

    class FakeLimiter:
        async def enforce_rate_limit(
            self, key: str, *, limit: int, window_seconds: int
        ) -> None:
            calls.append((key, limit, window_seconds))
            counts[key] = counts.get(key, 0) + 1
            if counts[key] > limit:
                raise RateLimitError("Too many requests")

    class FakePasswordResetService:
        def __init__(self, session) -> None:
            assert session is sentinel_session

        async def request_reset(self, email: str) -> None:
            requested_emails.append(email)

    sentinel_session = object()
    monkeypatch.setattr(auth, "_resolve_request_ip", lambda _: "203.0.113.10")
    monkeypatch.setattr(auth, "AntiAbuseService", FakeLimiter)
    monkeypatch.setattr(auth, "PasswordResetService", FakePasswordResetService)

    def make_request() -> Request:
        return Request(
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

    email_variants = [
        "Person@example.com",
        " person@example.com ",
        "PERSON@EXAMPLE.COM",
        "person@example.com",
    ]
    email_key = hashlib.sha256(b"person@example.com").hexdigest()

    for email in email_variants[:3]:
        result = await auth.request_password_reset(
            PasswordResetRequest(email=email), make_request(), sentinel_session
        )
        assert result["message"].startswith("Si existe una cuenta")

    # Different casing and surrounding whitespace must consume the same
    # per-email quota, even when requests arrive through the same IP.
    with pytest.raises(RateLimitError):
        await auth.request_password_reset(
            PasswordResetRequest(email=email_variants[3]),
            make_request(),
            sentinel_session,
        )

    expected_email_limit_key = f"password-reset:email:{email_key}"
    email_limit_calls = [call for call in calls if call[0].startswith("password-reset:email:")]
    assert email_limit_calls == [
        (expected_email_limit_key, 3, 900),
        (expected_email_limit_key, 3, 900),
        (expected_email_limit_key, 3, 900),
        (expected_email_limit_key, 3, 900),
    ]
    assert len(requested_emails) == 3
