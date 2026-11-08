"""Authenticated user preference endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.user_preferences import UserPreferences
from app.schemas.preferences import UserPreferencesResponse, UserPreferencesUpdate

router = APIRouter(prefix="/preferences", tags=["preferences"])


async def _get_or_create_preferences(session: AsyncSession, user_id: UUID) -> UserPreferences:
    preferences = await session.scalar(
        select(UserPreferences).where(UserPreferences.user_id == user_id)
    )
    if preferences is None:
        preferences = UserPreferences(user_id=user_id)
        session.add(preferences)
        await session.flush()
        await session.refresh(preferences)
    return preferences


@router.get("", response_model=UserPreferencesResponse)
async def get_preferences(user: CurrentUser, session: DbSession) -> UserPreferencesResponse:
    preferences = await _get_or_create_preferences(session, user.id)
    return UserPreferencesResponse.model_validate(preferences)


@router.patch("", response_model=UserPreferencesResponse)
async def update_preferences(
    body: UserPreferencesUpdate,
    user: CurrentUser,
    session: DbSession,
) -> UserPreferencesResponse:
    preferences = await _get_or_create_preferences(session, user.id)
    updates = body.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in updates.items():
        setattr(preferences, field, value)
    await session.flush()
    await session.refresh(preferences)
    return UserPreferencesResponse.model_validate(preferences)
