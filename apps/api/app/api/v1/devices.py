"""Cryptographic device identity enrollment endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.models.device import Device
from app.services.device_identity import DeviceIdentityService

router = APIRouter(prefix="/auth/devices", tags=["devices"])


class DeviceChallengeRequest(BaseModel):
    device_id: UUID
    public_key: str = Field(min_length=44, max_length=44)


class DeviceChallengeResponse(BaseModel):
    challenge_id: str
    nonce: str
    message: str
    algorithm: str
    expires_in: int


class DeviceChallengeVerifyRequest(BaseModel):
    challenge_id: str = Field(min_length=32, max_length=32)
    signature: str = Field(min_length=88, max_length=88)


class DeviceIdentityResponse(BaseModel):
    id: UUID
    device_id: str
    identity_verified: bool


@router.post("/challenge", response_model=DeviceChallengeResponse)
async def create_device_challenge(
    body: DeviceChallengeRequest,
    user: CurrentUser,
    session: DbSession,
) -> DeviceChallengeResponse:
    result = await DeviceIdentityService(session).create_challenge(
        user.id, body.device_id, body.public_key
    )
    return DeviceChallengeResponse(**result)


@router.post("/verify", response_model=DeviceIdentityResponse)
async def verify_device_challenge(
    body: DeviceChallengeVerifyRequest,
    user: CurrentUser,
    session: DbSession,
) -> DeviceIdentityResponse:
    device: Device = await DeviceIdentityService(session).verify_challenge(
        user.id, body.challenge_id, body.signature
    )
    return DeviceIdentityResponse(
        id=device.id,
        device_id=device.device_id,
        identity_verified=device.public_key is not None,
    )
