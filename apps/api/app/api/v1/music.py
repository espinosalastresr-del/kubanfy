"""Music Engine API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.services.anti_abuse import AntiAbuseService

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.providers.registry import ProviderManager, create_default_registry
from app.schemas.music import (
    MusicDownloadRequest,
    MusicDownloadResponse,
    MusicPreviewRequest,
    MusicPreviewResponse,
    MusicUpdateRequest,
    MusicUpdateResponse,
    TrackSearchResult,
)
from app.services.music_engine import MusicEngine

router = APIRouter(prefix="/music", tags=["music"])

# Shared manager for this process (mock included in non-prod by default)
_manager = ProviderManager(create_default_registry(include_mock=True))


@router.post("/update", response_model=MusicUpdateResponse)
async def music_update(
    body: MusicUpdateRequest,
    session: DbSession,
    user: OptionalUser,
) -> MusicUpdateResponse:
    engine = MusicEngine(session, provider_manager=_manager)
    result = await engine.update(
        provider=body.provider,
        provider_track_id=body.provider_track_id,
        query=body.query,
    )
    return MusicUpdateResponse(
        title=result.title,
        artists=result.artists,
        album=result.album,
        duration=result.duration,
        artwork=result.artwork,
        release_date=result.release_date,
        isrc=result.isrc,
        track_id=result.track_id,
        provider=result.provider,
        provider_track_id=result.provider_track_id,
        quality_capabilities=result.quality_capabilities,
        preview_available=result.preview_available,
        resolution_ref=result.resolution_ref,
    )


@router.post("/preview", response_model=MusicPreviewResponse)
async def music_preview(
    body: MusicPreviewRequest,
    session: DbSession,
    user: OptionalUser,
) -> MusicPreviewResponse:
    engine = MusicEngine(session, provider_manager=_manager)
    result = await engine.preview(
        provider=body.provider,
        provider_track_id=body.provider_track_id,
    )
    if result.source is None:
        return MusicPreviewResponse(available=False)
    return MusicPreviewResponse(
        available=True,
        url=result.source.url,
        expires_in_seconds=3600,
        duration_seconds=result.source.duration_seconds,
        codec=result.source.codec,
    )


@router.post("/download", response_model=MusicDownloadResponse)
async def music_download(
    body: MusicDownloadRequest,
    session: DbSession,
    user: CurrentUser,
) -> MusicDownloadResponse:
    """Requires authentication. Entitlement checks will be enforced here later."""
    engine = MusicEngine(session, provider_manager=_manager)
    result = await engine.download(
        provider=body.provider,
        provider_track_id=body.provider_track_id,
        quality=body.quality,
        user_id=user.id,
    )
    return MusicDownloadResponse(
        url=result.signed_url.url if result.signed_url else None,
        expires_in_seconds=result.signed_url.expires_in_seconds if result.signed_url else None,
        quality=result.quality,
        from_cache=result.from_cache,
        track_id=result.track_id,
        storage_key=result.storage_key,
    )


@router.get("/search", response_model=list[TrackSearchResult])
async def music_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=50),
) -> list[TrackSearchResult]:
    ip = request.client.host if request.client else None
    await AntiAbuseService().check_search(ip)
    results = await _manager.search(q, limit=limit)
    return [
        TrackSearchResult(
            provider=name,
            provider_track_id=meta.provider_track_id,
            title=meta.title,
            artists=list(meta.artists),
            album=meta.album,
            duration=meta.duration_seconds,
            artwork=meta.artwork_url,
            isrc=meta.isrc,
        )
        for name, meta in results
    ]
