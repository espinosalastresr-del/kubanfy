"""Authentication endpoints: register, login, profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    service = AuthService(session)
    user = await service.register(body)
    return AuthService.to_response(user)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    service = AuthService(session)
    user, tokens = await service.login(body)
    return LoginResponse(user=AuthService.to_response(user), tokens=tokens)
