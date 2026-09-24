"""Analytics ingestion and qualified engagement endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.services.anti_abuse import AntiAbuseService
from app.services.analytics import AnalyticsService
from app.services.engagement import EngagementService
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


    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and len(value) > 32:
            raise ValueError("metadata contains too many keys")
        return value

class AnalyticsBatchIn(BaseModel):
    events: list[AnalyticsEventIn] = Field(max_length=100)


class PlaybackStartIn(BaseModel):
    track_id: UUID
    quality: str = Field(default="low", pattern="^(low|medium|lossless)$")
    device_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=64)


class PlaybackHeartbeatIn(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    position_ms: int = Field(ge=0)
    paused: bool = False
    completed: bool = False


class DownloadTicketIn(BaseModel):
    track_id: UUID
    quality: str = Field(default="low", pattern="^(low|medium|lossless)$")
    device_id: str | None = Field(default=None, max_length=128)


class DownloadCompleteIn(BaseModel):
    ticket: str = Field(min_length=20, max_length=256)
    size_bytes: int | None = Field(default=None, ge=0)
    device_id: str | None = Field(default=None, max_length=128)


class ShareCreateIn(BaseModel):
    track_id: UUID


class ShareOpenIn(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    recipient_key: str = Field(min_length=8, max_length=128)


@router.post("/events", status_code=202)
async def ingest_event(
    body: AnalyticsEventIn,
    request: Request,
    session: DbSession,
    user: OptionalUser,
) -> dict[str, str]:
    geo = GeoService()
    ip = request.client.host if request.client else None
    forwarded_for = request.headers.get("x-forwarded-for")
    real_ip = geo.resolve_client_ip(ip, forwarded_for=forwarded_for)
    country = geo.resolve(ip=real_ip).country
    await AntiAbuseService().check_analytics(
        real_ip, str(user.id) if user else None
    )
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
    forwarded_for = request.headers.get("x-forwarded-for")
    real_ip = geo.resolve_client_ip(ip, forwarded_for=forwarded_for)
    country = geo.resolve(ip=real_ip).country
    await AntiAbuseService().check_analytics(
        real_ip, str(user.id) if user else None
    )
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


@router.post("/playback/start")
async def start_playback(
    body: PlaybackStartIn,
    request: Request,
    session: DbSession,
    user: OptionalUser,
) -> dict[str, Any]:
    geo = GeoService()
    ip = request.client.host if request.client else None
    real_ip = geo.resolve_client_ip(ip, forwarded_for=request.headers.get("x-forwarded-for"))
    country = geo.resolve(ip=real_ip).country
    await AntiAbuseService().check_analytics(
        real_ip, str(user.id) if user else None
    )
    row, token = await EngagementService(session).start_playback(
        user_id=user.id if user else None,
        device_id=body.device_id,
        session_id=body.session_id,
        track_id=body.track_id,
        quality=body.quality,
        country=country,
    )
    return {
        "playback_token": token,
        "playback_session_id": str(row.id),
        "heartbeat_interval_seconds": 10,
        "qualifying_listen_seconds": 30,
        "asset_version": row.asset_version,
        "content_hash": row.content_hash,
    }


@router.post("/playback/heartbeat")
async def playback_heartbeat(
    body: PlaybackHeartbeatIn,
    session: DbSession,
) -> dict[str, Any]:
    await AntiAbuseService().check_playback(body.token)
    row = await EngagementService(session).heartbeat(
        token=body.token,
        position_ms=body.position_ms,
        paused=body.paused,
        completed=body.completed,
    )
    return {
        "qualified": row.qualified_at is not None,
        "listened_ms": row.listened_ms,
        "suspicious_score": row.suspicious_score,
    }


@router.post("/downloads/ticket")
async def issue_download_ticket(
    body: DownloadTicketIn,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    row, token = await EngagementService(session).issue_download_ticket(
        user_id=user.id,
        device_id=body.device_id,
        track_id=body.track_id,
        quality=body.quality,
    )
    return {
        "download_ticket": token,
        "expires_in_seconds": 24 * 60 * 60,
        "asset_version": row.asset_version,
        "content_hash": row.content_hash,
    }


@router.post("/downloads/complete")
async def complete_download(
    body: DownloadCompleteIn,
    request: Request,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    row = await EngagementService(session).complete_download(
        user_id=user.id,
        token=body.ticket,
        size_bytes=body.size_bytes,
        device_id=body.device_id or request.headers.get("X-Device-ID"),
    )
    return {"qualified": row.completed_at is not None}


@router.post("/shares")
async def create_share(
    body: ShareCreateIn,
    request: Request,
    session: DbSession,
    user: OptionalUser,
) -> dict[str, str]:
    ip = request.client.host if request.client else None
    real_ip = GeoService().resolve_client_ip(
        ip, forwarded_for=request.headers.get("x-forwarded-for")
    )
    await AntiAbuseService().check_share(real_ip)
    _, token = await EngagementService(session).create_share(
        user_id=user.id if user else None,
        track_id=body.track_id,
    )
    return {"token": token, "expires_in_seconds": 30 * 24 * 60 * 60}


@router.post("/shares/open")
async def open_share(
    body: ShareOpenIn,
    session: DbSession,
    user: OptionalUser,
) -> dict[str, Any]:
    row = await EngagementService(session).open_share(
        token=body.token,
        recipient_key=body.recipient_key,
        recipient_user_id=user.id if user else None,
    )
    return {
        "track_id": str(row.track_id),
        "qualified_share": row.qualified_share,
        "unique_recipients": row.open_count,
    }
