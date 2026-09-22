"""Analytics ingestion endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.deps import DbSession, OptionalUser
from app.services.analytics import AnalyticsService
from app.services.geo import GeoService

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsEventIn(BaseModel):
    event_type: str = Field(max_length=64)
    event_id: str | None = Field(default=None, max_length=64)
    session_id: str | None = Field(default=None, max_length=64)
    device_id: str | None = Field(default=None, max_length=128)
    track_id: UUID | None = None
    release_id: UUID | None = None
    artist_id: UUID | None = None
    app_version: str | None = Field(default=None, max_length=32)
    os: str | None = Field(default=None, max_length=32)
    platform: str | None = Field(default=None, max_length=32)
    metadata: dict[str, Any] | None = None


class AnalyticsBatchIn(BaseModel):
    events: list[AnalyticsEventIn] = Field(max_length=100)


@router.post("/events", status_code=202)
async def ingest_event(
    body: AnalyticsEventIn,
    request: Request,
    session: DbSession,
    user: OptionalUser,
) -> dict[str, str]:
    geo = GeoService()
    ip = request.client.host if request.client else None
    country = geo.resolve(ip=ip).country
    await AnalyticsService(session).ingest(
        body.event_type,
        event_id=body.event_id,
        user_id=user.id if user else None,
        session_id=body.session_id,
        device_id=body.device_id,
        track_id=body.track_id,
        release_id=body.release_id,
        artist_id=body.artist_id,
        country=country,
        app_version=body.app_version,
        os=body.os,
        platform=body.platform,
        metadata=body.metadata,
    )
    return {"status": "accepted"}


@router.post("/events/batch", status_code=202)
async def ingest_batch(
    body: AnalyticsBatchIn,
    request: Request,
    session: DbSession,
    user: OptionalUser,
) -> dict[str, int]:
    geo = GeoService()
    ip = request.client.host if request.client else None
    country = geo.resolve(ip=ip).country
    svc = AnalyticsService(session)
    raw = []
    for e in body.events:
        raw.append(
            {
                "event_type": e.event_type,
                "event_id": e.event_id,
                "user_id": str(user.id) if user else None,
                "session_id": e.session_id,
                "device_id": e.device_id,
                "track_id": str(e.track_id) if e.track_id else None,
                "release_id": str(e.release_id) if e.release_id else None,
                "artist_id": str(e.artist_id) if e.artist_id else None,
                "country": country,
                "app_version": e.app_version,
                "os": e.os,
                "platform": e.platform,
                "metadata": e.metadata,
            }
        )
    count = await svc.ingest_batch(raw)
    return {"accepted": count}
