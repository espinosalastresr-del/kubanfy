import hashlib

import pytest

from app.core.config import Environment, Settings
from app.services.kby import derive_key, pack, unpack


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        environment=Environment.TEST,
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
        kby_master_key="test-kby-master-secret",
    )


def test_kby_round_trip_and_integrity(settings: Settings) -> None:
    plaintext = b"KubanFy KBY integration audio fixture"
    digest = hashlib.sha256(plaintext).hexdigest()

    container = pack(
        plaintext,
        content_hash=digest,
        quality="low",
        content_type="audio/wav",
        settings=settings,
    )

    assert container.startswith(b"KBY1")
    header, restored = unpack(
        container,
        key=derive_key(digest, settings=settings),
        expected_content_hash=digest,
    )
    assert header.quality == "low"
    assert header.content_type == "audio/wav"
    assert restored == plaintext


def test_kby_rejects_tampering(settings: Settings) -> None:
    plaintext = b"fixture"
    digest = hashlib.sha256(plaintext).hexdigest()
    container = bytearray(
        pack(
            plaintext,
            content_hash=digest,
            quality="low",
            content_type="audio/wav",
            settings=settings,
        )
    )
    container[-1] ^= 0x01

    with pytest.raises(ValueError, match="authentication"):
        unpack(
            bytes(container),
            key=derive_key(digest, settings=settings),
            expected_content_hash=digest,
        )


def test_kby_rejects_wrong_key(settings: Settings) -> None:
    plaintext = b"fixture"
    digest = hashlib.sha256(plaintext).hexdigest()
    container = pack(
        plaintext,
        content_hash=digest,
        quality="low",
        content_type="audio/wav",
        settings=settings,
    )

    wrong = Settings(
        environment=Environment.TEST,
        jwt_secret_key="another-test-secret-key-with-at-least-32-characters",
        kby_master_key="different-kby-master-secret",
    )
    with pytest.raises(ValueError, match="authentication"):
        unpack(
            container,
            key=derive_key(digest, settings=wrong),
            expected_content_hash=digest,
        )


def test_kby_requires_master_secret() -> None:
    settings = Settings(
        environment=Environment.TEST,
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
        kby_master_key="",
    )
    with pytest.raises(ValueError, match="KBY_MASTER_KEY"):
        pack(
            b"fixture",
            content_hash=hashlib.sha256(b"fixture").hexdigest(),
            quality="low",
            content_type="audio/wav",
            settings=settings,
        )
