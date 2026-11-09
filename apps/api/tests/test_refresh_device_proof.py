"""Login and refresh proof-of-possession regression tests."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.core.config import Settings
from app.core.exceptions import AuthError
from app.models.device import DeviceStatus, SessionStatus
from app.models.user import UserStatus
from app.schemas.auth import TokenResponse
from app.services.auth import AuthService
from app.services.device_identity import DeviceIdentityService


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, **kwargs) -> bool:
        if kwargs.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    async def eval(self, script: str, numkeys: int, key: str) -> str | None:
        return self.values.pop(key, None)


def keypair() -> tuple[Ed25519PrivateKey, str]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private, base64.b64encode(public).decode("ascii")


@pytest.mark.asyncio
async def test_login_challenge_proves_device_key_and_is_single_use(monkeypatch) -> None:
    import app.services.device_identity as module

    redis = FakeRedis()
    monkeypatch.setattr(module, "get_redis", lambda: redis)
    private, public_b64 = keypair()
    service = DeviceIdentityService(None)
    challenge = await service.create_login_challenge("browser-1", public_b64)
    signature = base64.b64encode(
        private.sign(challenge["message"].encode("utf-8"))
    ).decode("ascii")

    proven = await service.verify_login_challenge(
        "browser-1", challenge["challenge_id"], signature, public_b64
    )

    assert proven == public_b64
    with pytest.raises(AuthError) as error:
        await service.verify_login_challenge(
            "browser-1", challenge["challenge_id"], signature, public_b64
        )
    assert error.value.code == "DEVICE_CHALLENGE_INVALID"


@pytest.mark.asyncio
async def test_login_challenge_rejects_wrong_device_or_public_key(monkeypatch) -> None:
    import app.services.device_identity as module

    redis = FakeRedis()
    monkeypatch.setattr(module, "get_redis", lambda: redis)
    private, public_b64 = keypair()
    _, other_public_b64 = keypair()
    challenge = await DeviceIdentityService(None).create_login_challenge(
        "browser-1", public_b64
    )
    signature = base64.b64encode(
        private.sign(challenge["message"].encode("utf-8"))
    ).decode("ascii")

    with pytest.raises(AuthError) as error:
        await DeviceIdentityService(None).verify_login_challenge(
            "browser-2", challenge["challenge_id"], signature, other_public_b64
        )
    assert error.value.code == "DEVICE_CHALLENGE_INVALID"


@pytest.mark.asyncio
async def test_refresh_proof_is_bound_to_exact_token_and_session(monkeypatch) -> None:
    import app.services.device_identity as module

    redis = FakeRedis()
    monkeypatch.setattr(module, "get_redis", lambda: redis)
    private, public_b64 = keypair()
    user_id = uuid4()
    session_id = uuid4()
    device = SimpleNamespace(
        id=uuid4(), device_id="browser-1", public_key=public_b64,
        status=DeviceStatus.ACTIVE,
    )
    auth_session = SimpleNamespace(id=session_id)
    service = DeviceIdentityService(None)
    challenge = await service.create_refresh_challenge(
        user_id, auth_session, "refresh-jti-1", device
    )
    signature = base64.b64encode(
        private.sign(challenge["message"].encode("utf-8"))
    ).decode("ascii")

    await service.verify_refresh_challenge(
        user_id, auth_session, "refresh-jti-1", device,
        challenge["challenge_id"], signature,
    )

    with pytest.raises(AuthError) as error:
        await service.verify_refresh_challenge(
            user_id, auth_session, "refresh-jti-1", device,
            challenge["challenge_id"], signature,
        )
    assert error.value.code == "DEVICE_PROOF_INVALID"


@pytest.mark.asyncio
async def test_refresh_proof_rejects_replay_against_another_refresh_jti(monkeypatch) -> None:
    import app.services.device_identity as module

    redis = FakeRedis()
    monkeypatch.setattr(module, "get_redis", lambda: redis)
    private, public_b64 = keypair()
    user_id = uuid4()
    auth_session = SimpleNamespace(id=uuid4())
    device = SimpleNamespace(
        id=uuid4(), device_id="browser-1", public_key=public_b64,
        status=DeviceStatus.ACTIVE,
    )
    service = DeviceIdentityService(None)
    challenge = await service.create_refresh_challenge(
        user_id, auth_session, "refresh-jti-original", device
    )
    signature = base64.b64encode(
        private.sign(challenge["message"].encode("utf-8"))
    ).decode("ascii")

    with pytest.raises(AuthError) as error:
        await service.verify_refresh_challenge(
            user_id, auth_session, "refresh-jti-substituted", device,
            challenge["challenge_id"], signature,
        )
    assert error.value.code == "DEVICE_PROOF_INVALID"


@pytest.mark.asyncio
async def test_auth_refresh_refuses_device_session_without_signed_proof(monkeypatch) -> None:
    import app.services.auth as auth_module

    user_id = uuid4()
    device_id = uuid4()
    auth_session = SimpleNamespace(
        id=uuid4(), user_id=user_id, device_id=device_id,
        status=SessionStatus.ACTIVE, ip_country="CU", user_agent="test",
    )
    device = SimpleNamespace(
        id=device_id, device_id="browser-1", public_key="A" * 44,
        status=DeviceStatus.ACTIVE,
    )
    db = SimpleNamespace(get=AsyncMock(return_value=device), flush=AsyncMock())
    settings = Settings(
        environment="test",
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
    )
    service = AuthService(db, settings)
    service.sessions.validate_refresh_session = AsyncMock(return_value=auth_session)
    verify_proof = AsyncMock()
    monkeypatch.setattr(
        "app.services.auth.DeviceIdentityService.verify_refresh_challenge",
        verify_proof,
    )
    monkeypatch.setattr(
        auth_module,
        "decode_token",
        lambda *_args, **_kwargs: {
            "type": "refresh", "jti": "refresh-jti", "sub": str(user_id),
            "device_id": "browser-1",
        },
    )

    with pytest.raises(AuthError) as error:
        await service.refresh("refresh-token", device_id="browser-1")

    assert error.value.code == "DEVICE_PROOF_REQUIRED"
    verify_proof.assert_not_awaited()


@pytest.mark.asyncio
async def test_auth_refresh_verifies_proof_before_rotating_session(monkeypatch) -> None:
    import app.services.auth as auth_module

    user_id = uuid4()
    device_id = uuid4()
    auth_session = SimpleNamespace(
        id=uuid4(), user_id=user_id, device_id=device_id,
        status=SessionStatus.ACTIVE, ip_country="CU", user_agent="test",
    )
    device = SimpleNamespace(
        id=device_id, device_id="browser-1", public_key="A" * 44,
        status=DeviceStatus.ACTIVE,
    )
    user = SimpleNamespace(
        id=user_id, status=UserStatus.ACTIVE, email_verified=True,
    )
    db = SimpleNamespace(
        get=AsyncMock(side_effect=[device, user]),
        flush=AsyncMock(),
    )
    settings = Settings(
        environment="test",
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
    )
    service = AuthService(db, settings)
    service.sessions.validate_refresh_session = AsyncMock(return_value=auth_session)
    service.sessions.create_session = AsyncMock()
    tokens = TokenResponse(access_token="new-access", refresh_token="new-refresh", expires_in=1800)
    service._issue_tokens = Mock(return_value=(tokens, "new-jti", "new-access-jti"))
    verify_proof = AsyncMock()
    monkeypatch.setattr(
        "app.services.auth.DeviceIdentityService.verify_refresh_challenge",
        verify_proof,
    )
    monkeypatch.setattr(
        auth_module,
        "decode_token",
        lambda *_args, **_kwargs: {
            "type": "refresh", "jti": "old-jti", "sub": str(user_id),
            "device_id": "browser-1",
        },
    )

    result = await service.refresh(
        "old-refresh", device_id="browser-1",
        challenge_id="a" * 32, signature="b" * 88,
    )

    assert result == tokens
    verify_proof.assert_awaited_once()
    service.sessions.create_session.assert_awaited_once()
    assert auth_session.status == SessionStatus.REVOKED
