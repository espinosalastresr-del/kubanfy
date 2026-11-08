"""Device identity challenge-response and preference schema tests."""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import ValidationError

from app.core.exceptions import AuthError
from app.models.device import DeviceStatus
from app.schemas.preferences import UserPreferencesUpdate
from app.services.device_identity import DeviceIdentityService


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, **kwargs) -> bool:
        self.values[key] = value
        return True

    async def eval(self, script: str, numkeys: int, key: str) -> str | None:
        return self.values.pop(key, None)


def _keypair() -> tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private_key, base64.b64encode(public_key).decode("ascii")


@pytest.mark.asyncio
async def test_device_enrollment_requires_valid_ed25519_signature(monkeypatch) -> None:
    import app.services.device_identity as module

    user_id = uuid4()
    device_id = uuid4()
    device = SimpleNamespace(
        id=device_id,
        user_id=user_id,
        status=DeviceStatus.ACTIVE,
        public_key=None,
    )
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=device),
        flush=AsyncMock(),
    )
    redis = FakeRedis()
    monkeypatch.setattr(module, "get_redis", lambda: redis)
    private_key, public_key_b64 = _keypair()
    service = DeviceIdentityService(db)

    challenge = await service.create_challenge(user_id, device_id, public_key_b64)
    signature = base64.b64encode(
        private_key.sign(challenge["message"].encode("utf-8"))
    ).decode("ascii")

    verified = await service.verify_challenge(
        user_id, challenge["challenge_id"], signature
    )

    assert verified.public_key == public_key_b64
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_device_challenge_is_single_use(monkeypatch) -> None:
    import app.services.device_identity as module

    user_id = uuid4()
    device_id = uuid4()
    device = SimpleNamespace(
        id=device_id,
        user_id=user_id,
        status=DeviceStatus.ACTIVE,
        public_key=None,
    )
    db = SimpleNamespace(scalar=AsyncMock(return_value=device), flush=AsyncMock())
    redis = FakeRedis()
    monkeypatch.setattr(module, "get_redis", lambda: redis)
    private_key, public_key_b64 = _keypair()
    service = DeviceIdentityService(db)

    challenge = await service.create_challenge(user_id, device_id, public_key_b64)
    signature = base64.b64encode(
        private_key.sign(challenge["message"].encode("utf-8"))
    ).decode("ascii")
    await service.verify_challenge(user_id, challenge["challenge_id"], signature)

    with pytest.raises(AuthError) as error:
        await service.verify_challenge(user_id, challenge["challenge_id"], signature)

    assert error.value.code == "DEVICE_CHALLENGE_INVALID"


@pytest.mark.asyncio
async def test_device_challenge_rejects_signature_from_another_key(monkeypatch) -> None:
    import app.services.device_identity as module

    user_id = uuid4()
    device_id = uuid4()
    device = SimpleNamespace(
        id=device_id,
        user_id=user_id,
        status=DeviceStatus.ACTIVE,
        public_key=None,
    )
    db = SimpleNamespace(scalar=AsyncMock(return_value=device), flush=AsyncMock())
    redis = FakeRedis()
    monkeypatch.setattr(module, "get_redis", lambda: redis)
    _, public_key_b64 = _keypair()
    wrong_private_key, _ = _keypair()
    service = DeviceIdentityService(db)

    challenge = await service.create_challenge(user_id, device_id, public_key_b64)
    wrong_signature = base64.b64encode(
        wrong_private_key.sign(challenge["message"].encode("utf-8"))
    ).decode("ascii")

    with pytest.raises(AuthError) as error:
        await service.verify_challenge(
            user_id, challenge["challenge_id"], wrong_signature
        )

    assert error.value.code == "DEVICE_PROOF_INVALID"
    assert device.public_key is None


def test_preferences_update_rejects_user_id_override() -> None:
    with pytest.raises(ValidationError):
        UserPreferencesUpdate.model_validate(
            {"data_saver": False, "user_id": str(uuid4())}
        )


def test_preferences_update_accepts_partial_fields() -> None:
    update = UserPreferencesUpdate.model_validate(
        {"audio_quality": "low", "wifi_only_downloads": True}
    )

    assert update.model_dump(exclude_unset=True) == {
        "audio_quality": "low",
        "wifi_only_downloads": True,
    }
