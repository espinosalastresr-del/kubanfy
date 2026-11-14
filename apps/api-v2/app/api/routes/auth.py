from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select

from app.api.deps import CurrentIdentity, DbSession
from app.core.config import settings
from app.core.security import hash_session_token
from app.models import UserSession
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    SessionRead,
    UserRead,
)
from app.services.auth import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["authentication"])


def attach_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, request: Request, response: Response, db: DbSession
) -> AuthResponse:
    user, session, token = await register_user(db, payload, request)
    attach_session_cookie(response, token, session.expires_at)
    return AuthResponse(
        message="Cuenta creada correctamente.",
        user=UserRead.model_validate(user),
        terms_version=user.accepted_terms_version,
        terms_status="provisional",
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest, request: Request, response: Response, db: DbSession
) -> AuthResponse:
    user, session, token = await authenticate_user(db, payload, request)
    attach_session_cookie(response, token, session.expires_at)
    return AuthResponse(
        message="Sesión iniciada correctamente.",
        user=UserRead.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: DbSession) -> Response:
    token = request.cookies.get(settings.cookie_name)
    if token:
        session = await db.scalar(
            select(UserSession).where(
                UserSession.token_hash == hash_session_token(token),
                UserSession.revoked_at.is_(None),
            )
        )
        if session is not None:
            session.revoked_at = datetime.now(UTC)
            await db.commit()
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse)
async def me(identity: CurrentIdentity) -> MeResponse:
    user, session = identity
    content_country = (
        user.preferred_content_country
        if user.content_country_mode == "manual" and user.preferred_content_country
        else session.last_country or user.country_of_origin
    )
    return MeResponse(
        user=UserRead.model_validate(user),
        session=SessionRead(
            id=session.id,
            expires_at=session.expires_at,
            detected_country=session.last_country,
            content_country=content_country,
        ),
    )
