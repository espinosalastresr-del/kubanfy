from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, hash_session_token, new_session_token, verify_password
from app.models import User, UserSession
from app.schemas.auth import LoginRequest, RegisterRequest
from app.utils.request_context import client_ip, detected_country


async def register_user(
    db: AsyncSession, payload: RegisterRequest, request: Request
) -> tuple[User, UserSession, str]:
    user = User(
        full_name=payload.full_name,
        age=payload.age,
        email=str(payload.email).strip().lower(),
        password_hash=hash_password(payload.password),
        country_of_origin=payload.country_of_origin,
        accepted_terms_version=settings.terms_version,
        accepted_terms_at=datetime.now(UTC),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta con ese correo electrónico.",
        ) from exc
    return await create_session(db, user, request, remember_me=True)


async def authenticate_user(
    db: AsyncSession, payload: LoginRequest, request: Request
) -> tuple[User, UserSession, str]:
    email = str(payload.email).strip().lower()
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos.",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La cuenta está desactivada.")
    return await create_session(db, user, request, remember_me=payload.remember_me)


async def create_session(
    db: AsyncSession, user: User, request: Request, remember_me: bool
) -> tuple[User, UserSession, str]:
    now = datetime.now(UTC)
    duration = (
        timedelta(days=settings.session_remember_days)
        if remember_me
        else timedelta(hours=settings.session_short_hours)
    )
    token = new_session_token()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=now + duration,
        last_seen_at=now,
        last_ip=client_ip(request),
        last_country=detected_country(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(user)
    await db.refresh(session)
    return user, session, token


async def find_active_session(db: AsyncSession, token: str) -> tuple[User, UserSession] | None:
    now = datetime.now(UTC)
    result = await db.execute(
        select(User, UserSession)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == hash_session_token(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
            User.is_active.is_(True),
        )
    )
    row = result.first()
    if row is None:
        return None
    user, session = row
    if now - session.last_seen_at > timedelta(minutes=5):
        session.last_seen_at = now
        await db.commit()
    return user, session
