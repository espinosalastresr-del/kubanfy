"""Browser and legacy login response contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.auth import BrowserLoginResponse, LoginResponse


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
