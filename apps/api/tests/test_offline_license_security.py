from datetime import timedelta
import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Environment, Settings
from app.core.security import (
    create_offline_license_token,
    decode_offline_license_token,
)


@pytest.fixture()
def license_settings() -> Settings:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return Settings(
        environment=Environment.TEST,
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
        offline_license_private_key=private_pem,
        offline_license_public_key=public_pem,
    )


def test_offline_license_uses_asymmetric_signature(license_settings: Settings) -> None:
    token = create_offline_license_token(
        "user-1",
        extra_claims={
            "license_id": "license-1",
            "device_id": "device-1",
            "track_id": "track-1",
            "asset_version": 3,
            "quality": "medium",
            "content_hash": "sha256:abc",
        },
        expires_delta=timedelta(hours=1),
        settings=license_settings,
    )

    payload = decode_offline_license_token(token, license_settings)

    assert payload["type"] == "offline_license"
    assert payload["sub"] == "user-1"
    assert payload["track_id"] == "track-1"


def test_offline_license_rejects_tampering(license_settings: Settings) -> None:
    token = create_offline_license_token(
        "user-1",
        extra_claims={"track_id": "track-1"},
        expires_delta=timedelta(hours=1),
        settings=license_settings,
    )
    header, payload, signature = token.split(".")
    tampered = ".".join((header, payload + "x", signature))

    with pytest.raises(ValueError, match="Invalid or expired offline license"):
        decode_offline_license_token(tampered, license_settings)


def test_offline_license_rejects_expired_token(license_settings: Settings) -> None:
    token = create_offline_license_token(
        "user-1",
        extra_claims={"track_id": "track-1"},
        expires_delta=timedelta(seconds=-1),
        settings=license_settings,
    )

    with pytest.raises(ValueError, match="Invalid or expired offline license"):
        decode_offline_license_token(token, license_settings)


def test_production_requires_offline_license_keypair() -> None:
    with pytest.raises(ValueError, match="OFFLINE_LICENSE_PRIVATE_KEY"):
        Settings(
            environment=Environment.PRODUCTION,
            jwt_secret_key="production-secret-key-with-at-least-32-characters",
            super_admin_password="strong-production-password",
        )


def test_offline_license_rejects_reserved_claim_override(license_settings: Settings) -> None:
    with pytest.raises(ValueError, match="reserved claims"):
        create_offline_license_token(
            "user-1",
            extra_claims={"sub": "attacker"},
            expires_delta=timedelta(hours=1),
            settings=license_settings,
        )


def test_offline_license_rejects_missing_required_binding_claims(license_settings: Settings) -> None:
    token = create_offline_license_token(
        "user-1",
        extra_claims={"track_id": "track-1"},
        expires_delta=timedelta(hours=1),
        settings=license_settings,
    )
    with pytest.raises(ValueError, match="Invalid offline license claims"):
        decode_offline_license_token(token, license_settings)


def test_offline_license_rejects_invalid_asset_version(license_settings: Settings) -> None:
    token = create_offline_license_token(
        "user-1",
        extra_claims={
            "license_id": "license-1",
            "device_id": "device-1",
            "track_id": "track-1",
            "asset_version": 0,
            "quality": "medium",
            "content_hash": "sha256:abc",
        },
        expires_delta=timedelta(hours=1),
        settings=license_settings,
    )
    with pytest.raises(ValueError, match="Invalid offline license asset version"):
        decode_offline_license_token(token, license_settings)


@pytest.mark.asyncio
async def test_offline_license_public_key_endpoint_exposes_only_verification_key(
    monkeypatch: pytest.MonkeyPatch,
    license_settings: Settings,
) -> None:
    from fastapi import Response

    from app.api.v1 import offline as offline_api

    monkeypatch.setattr(offline_api, "get_settings", lambda: license_settings)
    response = Response()
    payload = await offline_api.offline_license_public_key(response)

    assert payload["algorithm"] == "RS256"
    assert payload["public_key"] == license_settings.offline_license_public_key
    assert payload["key_id"] == hashlib.sha256(
        license_settings.offline_license_public_key.encode("utf-8")
    ).hexdigest()[:16]
    assert "PRIVATE KEY" not in payload["public_key"]
    assert response.headers["Cache-Control"].startswith("public, max-age=3600")


@pytest.mark.asyncio
async def test_offline_license_public_key_endpoint_fails_closed_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException, Response

    from app.api.v1 import offline as offline_api

    settings = Settings(
        environment=Environment.TEST,
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
    )
    monkeypatch.setattr(offline_api, "get_settings", lambda: settings)
    with pytest.raises(HTTPException) as exc:
        await offline_api.offline_license_public_key(Response())
    assert exc.value.status_code == 503
