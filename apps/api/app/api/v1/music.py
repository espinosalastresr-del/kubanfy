"""Music Engine API endpoints."""

from __future__ import annotations

from uuid import UUID

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
    if body.track_id is not None:
        # Catalog track: try download path for a playable URL (preview-grade)
        try:
            result = await engine.download_by_track_id(
                track_id=body.track_id, quality="low"
            )
            if result.signed_url:
                return MusicPreviewResponse(
                    available=True,
                    url=result.signed_url.url,
                    expires_in_seconds=result.signed_url.expires_in_seconds,
                )
        except Exception:
            return MusicPreviewResponse(available=False)
    if not body.provider or not body.provider_track_id:
        return MusicPreviewResponse(available=False)
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
    request: Request,
    user: CurrentUser,
) -> MusicDownloadResponse:
    """Requires authentication. Entitlement checks enforced via engine/API layer."""
    ip = request.client.host if request.client else None
    await AntiAbuseService().check_download(str(user.id), ip)
    engine = MusicEngine(session, provider_manager=_manager)
    if body.track_id is not None:
        result = await engine.download_by_track_id(
            track_id=body.track_id,
            quality=body.quality,
            user_id=user.id,
        )
    elif body.provider and body.provider_track_id:
        result = await engine.download(
            provider=body.provider,
            provider_track_id=body.provider_track_id,
            quality=body.quality,
            user_id=user.id,
        )
    else:
        from app.core.exceptions import ValidationError
        raise ValidationError("Provide track_id or provider + provider_track_id")
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


@router.get("/content/{track_id}")
async def music_content_stream(
    track_id: UUID,
    request: Request,
    session: DbSession,
    user: CurrentUser,
    quality: str = Query("medium"),
):
    """Stream audio with HTTP Range (resume). Uses cache object when available."""
    from fastapi.responses import Response, StreamingResponse

    from app.services.http_range import parse_bytes_range
    from app.storage import StorageBucket, get_storage
    from app.core.exceptions import NotFoundError, ValidationError

    ip = request.client.host if request.client else None
    await AntiAbuseService().check_download(str(user.id), ip)
    engine = MusicEngine(session, provider_manager=_manager)
    try:
        result = await engine.download_by_track_id(track_id=track_id, quality=quality)
    except Exception as exc:
        raise NotFoundError("Audio not available") from exc

    storage_key = result.storage_key
    if not storage_key:
        raise ValidationError("No local object; use POST /music/download for signed URL")

    storage = get_storage()
    if not hasattr(storage, "size") or not hasattr(storage, "get_range"):
        raise ValidationError("Range streaming not supported on this storage backend")

    total = await storage.size(storage_key, bucket=StorageBucket.CACHE)
    range_header = request.headers.get("range") or request.headers.get("Range")
    br = parse_bytes_range(range_header, total)

    if range_header and br is None:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{total}"})

    if br is None:
        data = await storage.get(storage_key, bucket=StorageBucket.CACHE)

        async def full():
            yield data

        return StreamingResponse(
            full(),
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(total),
                "Cache-Control": "private, max-age=60",
            },
        )

    data = await storage.get_range(
        storage_key, br.start, br.end, bucket=StorageBucket.CACHE
    )

    async def partial():
        yield data

    return StreamingResponse(
        partial(),
        status_code=206,
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": br.content_range_header(),
            "Content-Length": str(br.length),
            "Cache-Control": "private, max-age=60",
        },
    )
