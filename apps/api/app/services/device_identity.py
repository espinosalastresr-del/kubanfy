"""One-time Ed25519 proof-of-possession for device enrollment."""

from __future__ import annotations

import base64
import binascii
import json
import secrets
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ConflictError, ForbiddenError, NotFoundError
from app.core.redis import get_redis
from app.models.device import Device, DeviceStatus, Session


_CHALLENGE_TTL_SECONDS = 180
_CHALLENGE_PREFIX = "device-identity:v1:"
_CONSUME_CHALLENGE = """
local value = redis.call('GET', KEYS[1])
if value then
    redis.call('DEL', KEYS[1])
end
return value
"""


def _decode_b64(value: str, *, expected_length: int) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AuthError("Invalid device proof", code="DEVICE_PROOF_INVALID") from exc
    if len(decoded) != expected_length:
        raise AuthError("Invalid device proof", code="DEVICE_PROOF_INVALID")
    return decoded


class DeviceIdentityService:
    """Enroll a device public key only after a valid one-time signature."""

    def __init__(self, session: AsyncSession) -> None:
        self.db = session


    async def create_login_challenge(self, device_id: str, public_key_b64: str) -> dict[str, str | int]:
        """Issue a short-lived proof challenge for password login."""
        _decode_b64(public_key_b64, expected_length=32)
        challenge_id = uuid4().hex
        nonce = secrets.token_urlsafe(32)
        message = self._login_message(challenge_id, nonce, device_id, public_key_b64)
        payload = json.dumps({"device_id": device_id, "public_key": public_key_b64, "nonce": nonce}, separators=(",", ":"))
        stored = await get_redis().set(f"{_CHALLENGE_PREFIX}login:{challenge_id}", payload, ex=_CHALLENGE_TTL_SECONDS, nx=True)
        if not stored:
            raise AuthError("Could not create device challenge", code="DEVICE_CHALLENGE_UNAVAILABLE", status_code=503)
        return {"challenge_id": challenge_id, "nonce": nonce, "message": message.decode("utf-8"), "algorithm": "Ed25519", "expires_in": _CHALLENGE_TTL_SECONDS}

    async def verify_login_challenge(self, device_id: str, challenge_id: str, signature_b64: str, expected_public_key_b64: str) -> str:
        """Consume a login challenge and return the public key whose possession was proven."""
        if len(challenge_id) != 32 or not all(c in "0123456789abcdef" for c in challenge_id):
            raise AuthError("Invalid or expired device challenge", code="DEVICE_CHALLENGE_INVALID")
        payload_raw = await get_redis().eval(_CONSUME_CHALLENGE, 1, f"{_CHALLENGE_PREFIX}login:{challenge_id}")
        if not payload_raw:
            raise AuthError("Invalid or expired device challenge", code="DEVICE_CHALLENGE_INVALID")
        try:
            payload = json.loads(payload_raw)
            stored_device_id, public_key_b64, nonce = payload["device_id"], payload["public_key"], payload["nonce"]
        except (ValueError, KeyError, TypeError) as exc:
            raise AuthError("Invalid device challenge", code="DEVICE_CHALLENGE_INVALID") from exc
        if stored_device_id != device_id or public_key_b64 != expected_public_key_b64:
            raise AuthError("Device challenge mismatch", code="DEVICE_CHALLENGE_INVALID")
        self._verify_signature(public_key_b64, signature_b64, self._login_message(challenge_id, nonce, device_id, public_key_b64))
        return public_key_b64

    async def create_refresh_challenge(self, user_id: UUID, auth_session: Session, refresh_jti: str, device: Device) -> dict[str, str | int]:
        """Issue a one-time challenge bound to one refresh token and persisted session."""
        if device.status != DeviceStatus.ACTIVE or not device.public_key:
            raise AuthError("Device identity must be enrolled before refreshing", code="DEVICE_IDENTITY_REQUIRED")
        challenge_id = uuid4().hex
        nonce = secrets.token_urlsafe(32)
        message = self._refresh_message(challenge_id, nonce, user_id, auth_session.id, refresh_jti, device.device_id, device.public_key)
        payload = json.dumps({
            "user_id": str(user_id), "session_id": str(auth_session.id), "refresh_jti": refresh_jti,
            "device_db_id": str(device.id), "device_id": device.device_id, "public_key": device.public_key, "nonce": nonce,
        }, separators=(",", ":"))
        stored = await get_redis().set(f"{_CHALLENGE_PREFIX}refresh:{challenge_id}", payload, ex=90, nx=True)
        if not stored:
            raise AuthError("Could not create refresh challenge", code="DEVICE_CHALLENGE_UNAVAILABLE", status_code=503)
        return {"challenge_id": challenge_id, "nonce": nonce, "message": message.decode("utf-8"), "algorithm": "Ed25519", "expires_in": 90}

    async def verify_refresh_challenge(self, user_id: UUID, auth_session: Session, refresh_jti: str, device: Device, challenge_id: str, signature_b64: str) -> None:
        """Consume and verify proof bound to this exact refresh token and session."""
        if len(challenge_id) != 32 or not all(c in "0123456789abcdef" for c in challenge_id):
            raise AuthError("Invalid or expired refresh proof", code="DEVICE_PROOF_INVALID")
        payload_raw = await get_redis().eval(_CONSUME_CHALLENGE, 1, f"{_CHALLENGE_PREFIX}refresh:{challenge_id}")
        if not payload_raw:
            raise AuthError("Invalid or expired refresh proof", code="DEVICE_PROOF_INVALID")
        try:
            payload = json.loads(payload_raw)
            nonce = payload["nonce"]
            bound = (
                payload["user_id"] == str(user_id) and payload["session_id"] == str(auth_session.id)
                and payload["refresh_jti"] == refresh_jti and payload["device_db_id"] == str(device.id)
                and payload["device_id"] == device.device_id and payload["public_key"] == device.public_key
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise AuthError("Invalid refresh proof", code="DEVICE_PROOF_INVALID") from exc
        if not bound or device.status != DeviceStatus.ACTIVE or not device.public_key:
            raise AuthError("Refresh proof does not match this session", code="DEVICE_PROOF_INVALID")
        self._verify_signature(device.public_key, signature_b64, self._refresh_message(
            challenge_id, nonce, user_id, auth_session.id, refresh_jti, device.device_id, device.public_key
        ))

    @staticmethod
    def _verify_signature(public_key_b64: str, signature_b64: str, message: bytes) -> None:
        public_key_bytes = _decode_b64(public_key_b64, expected_length=32)
        signature = _decode_b64(signature_b64, expected_length=64)
        try:
            Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, message)
        except (InvalidSignature, ValueError) as exc:
            raise AuthError("Invalid device signature", code="DEVICE_PROOF_INVALID") from exc

    @staticmethod
    def _login_message(challenge_id: str, nonce: str, device_id: str, public_key_b64: str) -> bytes:
        return ("KUBANFY-DEVICE-LOGIN-V1\n" f"{challenge_id}\n{nonce}\n{device_id}\n{public_key_b64}").encode("utf-8")

    @staticmethod
    def _refresh_message(challenge_id: str, nonce: str, user_id: UUID, session_id: UUID, refresh_jti: str, device_id: str, public_key_b64: str) -> bytes:
        return ("KUBANFY-REFRESH-POP-V1\n" f"{challenge_id}\n{nonce}\n{user_id}\n{session_id}\n{refresh_jti}\n{device_id}\n{public_key_b64}").encode("utf-8")

    async def create_challenge(
        self, user_id: UUID, device_id: UUID, public_key_b64: str
    ) -> dict[str, str]:
        _decode_b64(public_key_b64, expected_length=32)
        device = await self.db.scalar(
            select(Device).where(Device.id == device_id, Device.user_id == user_id)
        )
        if device is None:
            raise NotFoundError("Device not found")
        if device.status == DeviceStatus.BLOCKED:
            raise ForbiddenError("Device is blocked", code="DEVICE_BLOCKED")
        if device.status != DeviceStatus.ACTIVE:
            raise ForbiddenError("Device is not active", code="DEVICE_NOT_ACTIVE")
        if device.public_key is not None and device.public_key != public_key_b64:
            raise ConflictError(
                "This device is already bound to another cryptographic identity",
                code="DEVICE_KEY_CONFLICT",
            )

        challenge_id = uuid4().hex
        nonce = secrets.token_urlsafe(32)
        message = self._message(challenge_id, nonce, user_id, device_id)
        payload = json.dumps(
            {
                "user_id": str(user_id),
                "device_id": str(device_id),
                "public_key": public_key_b64,
                "nonce": nonce,
            },
            separators=(",", ":"),
        )
        await get_redis().set(
            f"{_CHALLENGE_PREFIX}{challenge_id}",
            payload,
            ex=_CHALLENGE_TTL_SECONDS,
            nx=True,
        )
        return {
            "challenge_id": challenge_id,
            "nonce": nonce,
            "message": message.decode("utf-8"),
            "algorithm": "Ed25519",
            "expires_in": _CHALLENGE_TTL_SECONDS,
        }

    async def verify_challenge(
        self, user_id: UUID, challenge_id: str, signature_b64: str
    ) -> Device:
        if len(challenge_id) != 32 or not all(c in "0123456789abcdef" for c in challenge_id):
            raise AuthError("Invalid or expired device challenge", code="DEVICE_CHALLENGE_INVALID")

        payload_raw = await get_redis().eval(
            _CONSUME_CHALLENGE, 1, f"{_CHALLENGE_PREFIX}{challenge_id}"
        )
        if not payload_raw:
            raise AuthError("Invalid or expired device challenge", code="DEVICE_CHALLENGE_INVALID")

        try:
            payload = json.loads(payload_raw)
            challenge_user_id = UUID(payload["user_id"])
            device_id = UUID(payload["device_id"])
            public_key_b64 = payload["public_key"]
            nonce = payload["nonce"]
        except (ValueError, KeyError, TypeError) as exc:
            raise AuthError("Invalid device challenge", code="DEVICE_CHALLENGE_INVALID") from exc

        if challenge_user_id != user_id:
            raise AuthError("Invalid or expired device challenge", code="DEVICE_CHALLENGE_INVALID")

        device = await self.db.scalar(
            select(Device).where(Device.id == device_id, Device.user_id == user_id)
        )
        if device is None:
            raise NotFoundError("Device not found")
        if device.status == DeviceStatus.BLOCKED:
            raise ForbiddenError("Device is blocked", code="DEVICE_BLOCKED")
        if device.status != DeviceStatus.ACTIVE:
            raise ForbiddenError("Device is not active", code="DEVICE_NOT_ACTIVE")
        if device.public_key is not None and device.public_key != public_key_b64:
            raise ConflictError("Device identity has changed", code="DEVICE_KEY_CONFLICT")

        message = self._message(challenge_id, nonce, user_id, device_id)
        self._verify_signature(public_key_b64, signature_b64, message)

        device.public_key = public_key_b64
        await self.db.flush()
        return device

    @staticmethod
    def _message(challenge_id: str, nonce: str, user_id: UUID, device_id: UUID) -> bytes:
        return (
            "KUBANFY-DEVICE-ENROLL-V1\n"
            f"{challenge_id}\n{nonce}\n{user_id}\n{device_id}"
        ).encode("utf-8")
