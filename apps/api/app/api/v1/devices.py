"""Cryptographic device identity enrollment endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.models.device import Device
from app.services.anti_abuse import AntiAbuseService
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



class DeviceLoginChallengeRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    public_key: str = Field(min_length=44, max_length=44)


@router.post("/login-challenge", response_model=DeviceChallengeResponse)
async def create_login_challenge(body: DeviceLoginChallengeRequest, request: Request) -> DeviceChallengeResponse:
    limiter = AntiAbuseService()
    await limiter.enforce_rate_limit(
        f"device-login-challenge:device:{body.device_id}", limit=10, window_seconds=900
    )
    ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else None)
    if ip:
        await limiter.enforce_rate_limit(f"device-login-challenge:ip:{ip}", limit=30, window_seconds=900)
    result = await DeviceIdentityService(None).create_login_challenge(body.device_id, body.public_key)
    return DeviceChallengeResponse(**result)


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
    await AntiAbuseService().enforce_rate_limit(
        f"device-identity:challenge:user:{user.id}", limit=5, window_seconds=900
    )
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
    await AntiAbuseService().enforce_rate_limit(
        f"device-identity:verify:user:{user.id}", limit=10, window_seconds=900
    )
    device: Device = await DeviceIdentityService(session).verify_challenge(
        user.id, body.challenge_id, body.signature
    )
    return DeviceIdentityResponse(
        id=device.id,
        device_id=device.device_id,
        identity_verified=device.public_key is not None,
    )
