"""Music Engine API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.core.exceptions import AuthError
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
from app.services.anti_abuse import AntiAbuseService
from app.services.entitlement import EntitlementService
from app.services.music_engine import MusicEngine
from app.services.offline_license import OfflineLicenseService

router = APIRouter(prefix="/music", tags=["music"])


def _audio_media_type(result) -> str:
    key = (result.storage_key or "").lower()
    if key.endswith(".flac"):
        return "audio/flac"
    if key.endswith(".m4a") or key.endswith(".mp4"):
        return "audio/mp4"
    if key.endswith(".ogg") or key.endswith(".oga"):
        return "audio/ogg"
    if key.endswith(".opus"):
        return "audio/opus"
    if key.endswith(".wav"):
        return "audio/wav"
    return "audio/mpeg"


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
    """Requires authentication and an entitlement for catalog downloads."""
    ip = request.client.host if request.client else None
    await AntiAbuseService().check_download(str(user.id), ip)
    engine = MusicEngine(session, provider_manager=_manager)
    if body.track_id is not None:
        await EntitlementService(session).require_track_access(user.id, body.track_id)
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

    size_bytes = None
    if result.storage_key:
        from app.storage import get_storage

        storage = get_storage()
        size_bytes = await storage.size(
            result.storage_key,
            bucket=result.storage_bucket,
        )

    offline_license = None
    offline_license_expires_at = None
    device_id = body.device_id or request.headers.get("X-Device-ID")
    if device_id is not None:
        authorization = request.headers.get("Authorization", "")
        try:
            token = authorization.split(" ", 1)[1]
            from app.core.security import decode_token

            claims = decode_token(token)
        except (IndexError, ValueError) as exc:
            raise AuthError("Invalid authorization token") from exc
        token_device_id = claims.get("device_id")
        if token_device_id != device_id:
            raise AuthError("Offline license device mismatch")
        if body.track_id is None:
            from app.core.exceptions import ValidationError

            raise ValidationError("Device-bound offline licenses require a first-party track_id")
        license_row, offline_license = await OfflineLicenseService(session).issue(
            user_id=user.id,
            device_id=device_id,
            track_id=body.track_id,
            quality=body.quality,
        )
        offline_license_expires_at = license_row.expires_at.isoformat()

    return MusicDownloadResponse(
        url=result.signed_url.url if result.signed_url else None,
        expires_in_seconds=(result.signed_url.expires_in_seconds if result.signed_url else None),
        quality=result.quality,
        from_cache=result.from_cache,
        track_id=result.track_id,
        storage_key=result.storage_key,
        content_hash=result.content_hash,
        size_bytes=size_bytes,
        offline_license=offline_license,
        offline_license_expires_at=offline_license_expires_at,
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

    from app.core.exceptions import NotFoundError, ValidationError
    from app.services.http_range import parse_bytes_range
    from app.storage import get_storage

    async def storage_range_stream(storage, key, start, end, bucket):
        yield await storage.get_range(
            key,
            start,
            end,
            bucket=bucket,
        )

    ip = request.client.host if request.client else None
    await AntiAbuseService().check_download(str(user.id), ip)
    engine = MusicEngine(session, provider_manager=_manager)
    await EntitlementService(session).require_track_access(user.id, track_id)
    try:
        result = await engine.download_by_track_id(track_id=track_id, quality=quality)
    except Exception as exc:
        raise NotFoundError("Audio not available") from exc

    storage_key = result.storage_key
    if not storage_key:
        raise ValidationError("No local object; use POST /music/download for signed URL")

    storage = get_storage()
    total = await storage.size(storage_key, bucket=result.storage_bucket)
    range_header = request.headers.get("range") or request.headers.get("Range")
    br = parse_bytes_range(range_header, total)

    if range_header and br is None:
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{total}"},
        )

    common_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=60",
    }
    if result.content_hash:
        common_headers["ETag"] = f'"{result.content_hash}"'

    if br is None:
        headers = {
            **common_headers,
            "Content-Length": str(total),
        }
        return StreamingResponse(
            storage.stream(
                storage_key,
                bucket=result.storage_bucket,
                chunk_size=65536,
            ),
            media_type=_audio_media_type(result),
            headers=headers,
        )

    headers = {
        **common_headers,
        "Content-Range": br.content_range_header(),
        "Content-Length": str(br.length),
    }
    return StreamingResponse(
        storage_range_stream(storage, storage_key, br.start, br.end, result.storage_bucket),
        status_code=206,
        media_type=_audio_media_type(result),
        headers=headers,
    )
