"""Password hashing and JWT helpers.

Never store passwords in plain text.
Uses bcrypt directly (passlib has compatibility issues with bcrypt >= 4.1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import Settings, get_settings


def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Truncate to 72 bytes as required by bcrypt."""
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        password_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_offline_license_token(
    subject: str,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta,
    settings: Settings | None = None,
) -> str:
    """Create an offline license with an asymmetric signature.

    The private key must remain server-side. Mobile clients only receive the
    corresponding public key, so compromise of the app cannot mint licenses.
    """
    settings = settings or get_settings()
    if settings.offline_license_algorithm != "RS256":
        raise ValueError("Offline license algorithm must be RS256")
    if not settings.offline_license_private_key:
        raise ValueError("OFFLINE_LICENSE_PRIVATE_KEY is not configured")

    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid4()),
        "type": "offline_license",
    }
    if extra_claims:
        reserved = {"sub", "iat", "exp", "jti", "type"}
        if reserved.intersection(extra_claims):
            raise ValueError("Offline license extra claims cannot override reserved claims")
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        settings.offline_license_private_key,
        algorithm=settings.offline_license_algorithm,
    )


def decode_offline_license_token(
    token: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Verify an offline license using only the server-side public key."""
    settings = settings or get_settings()
    if settings.offline_license_algorithm != "RS256":
        raise ValueError("Offline license algorithm must be RS256")
    if not settings.offline_license_public_key:
        raise ValueError("OFFLINE_LICENSE_PUBLIC_KEY is not configured")
    try:
        payload = jwt.decode(
            token,
            settings.offline_license_public_key,
            algorithms=[settings.offline_license_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired offline license") from exc
    required_string_claims = (
        "sub",
        "jti",
        "type",
        "license_id",
        "device_id",
        "track_id",
        "quality",
        "content_hash",
    )
    if any(not isinstance(payload.get(name), str) or not payload[name] for name in required_string_claims):
        raise ValueError("Invalid offline license claims")
    asset_version = payload.get("asset_version")
    if not isinstance(asset_version, int) or isinstance(asset_version, bool) or asset_version < 1:
        raise ValueError("Invalid offline license asset version")
    if payload.get("type") != "offline_license":
        raise ValueError("Invalid offline license type")
    return payload


def create_access_token(
    subject: str,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "jti": str(uuid4()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    subject: str,
    *,
    device_id: str | None = None,
    expires_delta: timedelta | None = None,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(days=settings.refresh_token_expire_days)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "jti": str(uuid4()),
        "type": "refresh",
    }
    if device_id:
        payload["device_id"] = device_id
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
