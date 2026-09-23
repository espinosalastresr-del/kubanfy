from datetime import timedelta

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
