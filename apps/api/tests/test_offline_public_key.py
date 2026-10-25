from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest

from app.api.v1.offline import resolve_offline_license_public_key
from app.core.exceptions import ProviderUnavailableError


def _keypair() -> tuple[str, str]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def test_public_key_is_derived_from_configured_private_key_when_public_binding_missing() -> None:
    private_pem, expected_public = _keypair()
    actual = resolve_offline_license_public_key(
        algorithm="RS256", public_key="", private_key=private_pem
    )
    assert actual == expected_public


def test_configured_public_key_is_preserved() -> None:
    private_pem, expected_public = _keypair()
    actual = resolve_offline_license_public_key(
        algorithm="RS256", public_key=expected_public, private_key=private_pem
    )
    assert actual == expected_public


@pytest.mark.parametrize(
    ("algorithm", "public_key", "private_key"),
    [
        ("HS256", "", "not-a-key"),
        ("RS256", "", ""),
        ("RS256", "", "not-a-key"),
    ],
)
def test_missing_or_invalid_offline_key_configuration_fails_closed(
    algorithm: str, public_key: str, private_key: str
) -> None:
    with pytest.raises(ProviderUnavailableError):
        resolve_offline_license_public_key(
            algorithm=algorithm, public_key=public_key, private_key=private_key
        )
