"""Unit tests for password hashing and JWT helpers."""

from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    password = "SecurePass123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_roundtrip() -> None:
    token = create_access_token("user-123", extra_claims={"email": "a@b.com"})
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["email"] == "a@b.com"
    assert "jti" in payload
    assert "exp" in payload


def test_refresh_token_roundtrip() -> None:
    token = create_refresh_token("user-456", device_id="device-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-456"
    assert payload["type"] == "refresh"
    assert payload["device_id"] == "device-1"


def test_invalid_token_raises() -> None:
    with pytest.raises(ValueError, match="Invalid or expired"):
        decode_token("not.a.valid.token")


def test_access_token_can_bind_device() -> None:
    token = create_access_token(
        "user-789",
        extra_claims={"device_id": "rn-device-1"},
    )
    payload = decode_token(token)
    assert payload["device_id"] == "rn-device-1"
