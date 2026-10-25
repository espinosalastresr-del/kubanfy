"""Authentication endpoints: register, login, refresh, profile, sessions, devices."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import (
    PasswordResetConfirmRequest,
    ProfileUpdateRequest,
    PasswordResetRequest,
    AuthContextResponse,
    DeviceResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    SessionResponse,
    TokenResponse,
    UserResponse,
)
from app.services.anti_abuse import AntiAbuseService
from app.services.auth import AuthService
from app.services.session import SessionService
from app.services.geo import GeoService
from app.services.password_reset import PasswordResetService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    session: DbSession,
) -> UserResponse:
    geo = GeoService()
    ip = request.client.host if request.client else None
    real_ip = geo.resolve_client_ip(ip, forwarded_for=request.headers.get("x-forwarded-for"))
    await AntiAbuseService().check_register(real_ip)
    service = AuthService(session)
    user = await service.register(body)
    return AuthService.to_response(user)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: DbSession,
) -> LoginResponse:
    geo = GeoService()
    ip = request.client.host if request.client else None
    real_ip = geo.resolve_client_ip(ip, forwarded_for=request.headers.get("x-forwarded-for"))
    await AntiAbuseService().check_login(real_ip, body.email)
    service = AuthService(session)
    user_agent = request.headers.get("user-agent")
    user, tokens = await service.login(body, ip_country=geo.resolve(ip=real_ip).country, user_agent=user_agent)
    return LoginResponse(user=AuthService.to_response(user), tokens=tokens)


@router.post("/password-reset/request", status_code=202)
async def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    session: DbSession,
) -> dict[str, str]:
    # Bound automated email abuse without revealing whether an account exists.
    ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else None)
    if ip:
        await AntiAbuseService().enforce_rate_limit(
            f"password-reset:ip:{ip}", limit=5, window_seconds=900
        )
    await PasswordResetService(session).request_reset(str(body.email))
    return {"message": "Si existe una cuenta para ese correo, recibirás instrucciones para restablecer la contraseña."}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    body: PasswordResetConfirmRequest,
    request: Request,
    session: DbSession,
) -> dict[str, str]:
    ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else None)
    if ip:
        await AntiAbuseService().enforce_rate_limit(
            f"password-reset-confirm:ip:{ip}", limit=10, window_seconds=900
        )
    changed = await PasswordResetService(session).consume(body.token, body.new_password)
    if not changed:
        from app.core.exceptions import AuthError

        raise AuthError("Invalid or expired password reset token")
    return {"message": "La contraseña se ha actualizado. Inicia sesión con tu nueva contraseña."}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    session: DbSession,
) -> TokenResponse:
    service = AuthService(session)
    return await service.refresh(body.refresh_token, device_id=body.device_id)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return AuthService.to_response(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: ProfileUpdateRequest,
    user: CurrentUser,
    session: DbSession,
) -> UserResponse:
    """Update only the signed-in user's editable profile fields."""
    user.display_name = body.display_name
    user.country = body.country
    user.language = body.language
    await session.flush()
    await session.refresh(user)
    return AuthService.to_response(user)


@router.get("/context", response_model=AuthContextResponse)
async def context(user: CurrentUser, session: DbSession) -> AuthContextResponse:
    service = AuthService(session)
    roles, artist_ids = await service.get_access_context(user.id)
    return AuthContextResponse(
        user=AuthService.to_response(user),
        roles=roles,
        artist_ids=artist_ids,
        is_artist=bool(artist_ids),
        is_admin=any(role in {"admin", "super_admin"} for role in roles),
    )


@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices(user: CurrentUser, session: DbSession) -> list[DeviceResponse]:
    svc = SessionService(session)
    devices = await svc.list_devices(user.id)
    return [DeviceResponse.model_validate(d) for d in devices]


@router.delete("/devices/{device_id}", status_code=204)
async def revoke_device(
    device_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> None:
    svc = SessionService(session)
    await svc.revoke_device(device_id, user.id)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(user: CurrentUser, session: DbSession) -> list[SessionResponse]:
    svc = SessionService(session)
    sessions = await svc.list_sessions(user.id)
    return [SessionResponse.model_validate(s) for s in sessions]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> None:
    svc = SessionService(session)
    await svc.revoke_session(session_id, user.id)


@router.post("/logout-all", status_code=204)
async def logout_all(user: CurrentUser, session: DbSession) -> None:
    svc = SessionService(session)
    await svc.revoke_all_sessions(user.id)
