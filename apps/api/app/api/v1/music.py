"""Music Engine API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.core.exceptions import AuthError
from app.providers.registry import ProviderManager, create_default_registry
from app.schemas.music import (
    MusicDownloadRequest,
    MusicDownloadResponse,
    MusicPreviewRequest,
    MusicPreviewResponse,
    MusicPlaybackResponse,
    MusicUpdateRequest,
    MusicUpdateResponse,
    TrackSearchResult,
)
from app.services.anti_abuse import AntiAbuseService
from app.services.engagement import EngagementService
from app.services.entitlement import EntitlementService
from app.services.geo import GeoService
from app.services.music_engine import MusicEngine
from app.services.offline_license import OfflineLicenseService
from app.models.music import Artist, Release, Track, TrackArtist
from app.storage import LocalStorage, get_storage

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


_manager = ProviderManager(create_default_registry(include_mock=False))


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


@router.get("/tracks/{track_id}")
async def music_track_detail(
    track_id: UUID,
    session: DbSession,
    user: OptionalUser,
) -> dict:
    """Return presentation metadata for a published track detail screen."""
    track = await session.scalar(
        select(Track).where(Track.id == track_id, Track.status == "published")
    )
    if track is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Track not found")

    rows = (
        await session.execute(
            select(Artist)
            .join(TrackArtist, TrackArtist.artist_id == Artist.id)
            .where(TrackArtist.track_id == track.id, Artist.status == "active")
            .order_by(TrackArtist.display_order, Artist.name)
        )
    ).scalars().all()
    return {
        "id": track.id,
        "title": track.title,
        "duration": track.duration,
        "isrc": track.isrc,
        "explicit": track.explicit,
        "language": track.language,
        "release_date": track.release_date,
        "artwork_url": track.artwork_url,
        "artists": [
            {"id": artist.id, "name": artist.name, "slug": artist.slug, "verified": artist.verified}
            for artist in rows
        ],
    }


@router.get("/play/{track_id}", response_model=MusicPlaybackResponse)
async def music_play(
    track_id: UUID,
    request: Request,
    session: DbSession,
    user: CurrentUser,
    quality: str = Query("low"),
) -> MusicPlaybackResponse:
    """Return a short-lived signed URL for authenticated streaming playback."""
    geo = GeoService()
    ip = request.client.host if request.client else None
    real_ip = geo.resolve_client_ip(ip, forwarded_for=request.headers.get("x-forwarded-for"))
    await AntiAbuseService().check_download(str(user.id), real_ip)
    entitlement = EntitlementService(session)
    await entitlement.require_track_access(user.id, track_id)
    await entitlement.require_quality_access(user.id, quality)
    engine = MusicEngine(session, provider_manager=_manager)
    result = await engine.download_by_track_id(
        track_id=track_id,
        quality=quality,
        user_id=user.id,
    )
    if result.signed_url is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Playable audio URL unavailable")
    return MusicPlaybackResponse(
        url=result.signed_url.url,
        expires_in_seconds=result.signed_url.expires_in_seconds,
        quality=result.quality,
        track_id=track_id,
        content_hash=result.content_hash,
        kby_key=result.kby_key or "",
    )


@router.post("/download", response_model=MusicDownloadResponse)
async def music_download(
    body: MusicDownloadRequest,
    session: DbSession,
    request: Request,
    user: CurrentUser,
) -> MusicDownloadResponse:
    """Requires authentication and premium entitlement for persistent downloads."""
    geo = GeoService()
    ip = request.client.host if request.client else None
    real_ip = geo.resolve_client_ip(ip, forwarded_for=request.headers.get("x-forwarded-for"))
    await AntiAbuseService().check_download(str(user.id), real_ip)
    entitlement = EntitlementService(session)
    await entitlement.require_download_access(user.id)
    await entitlement.require_quality_access(user.id, body.quality)
    engine = MusicEngine(session, provider_manager=_manager)
    if body.track_id is not None:
        await entitlement.require_track_access(user.id, body.track_id)
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

    download_ticket = None
    resolved_track_id = result.track_id or body.track_id
    if resolved_track_id is not None:
        _, download_ticket = await EngagementService(session).issue_download_ticket(
            user_id=user.id,
            device_id=body.device_id or request.headers.get("X-Device-ID"),
            track_id=resolved_track_id,
            quality=body.quality,
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
        kby_key=result.kby_key,
        size_bytes=size_bytes,
        download_ticket=download_ticket,
        offline_license=offline_license,
        offline_license_expires_at=offline_license_expires_at,
    )


@router.get("/search", response_model=list[TrackSearchResult])
async def music_search(
    request: Request,
    session: DbSession,
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=50),
) -> list[TrackSearchResult]:
    geo = GeoService()
    ip = request.client.host if request.client else None
    real_ip = geo.resolve_client_ip(ip, forwarded_for=request.headers.get("x-forwarded-for"))
    await AntiAbuseService().check_search(real_ip)

    normalized = q.strip()
    provider_results = await _manager.search(normalized, limit=limit)
    results = [
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
        for name, meta in provider_results
    ]

    remaining = max(0, limit - len(results))
    if remaining:
        pattern = f"%{normalized.lower()}%"
        rows = (
            await session.execute(
                select(Track, Release)
                .outerjoin(Release, Release.id == Track.release_id)
                .where(
                    Track.status == "published",
                    or_(
                        func.lower(Track.title).like(pattern),
                        Track.id.in_(
                            select(TrackArtist.track_id)
                            .join(Artist, Artist.id == TrackArtist.artist_id)
                            .where(
                                Artist.status == "active",
                                func.lower(Artist.name).like(pattern),
                            )
                        ),
                    ),
                )
                .order_by(Track.title)
                .limit(remaining)
            )
        ).all()

        for track, release in rows:
            artist_rows = (
                await session.execute(
                    select(Artist)
                    .join(TrackArtist, TrackArtist.artist_id == Artist.id)
                    .where(
                        TrackArtist.track_id == track.id,
                        Artist.status == "active",
                    )
                    .order_by(TrackArtist.display_order, Artist.name)
                )
            ).scalars().all()
            results.append(
                TrackSearchResult(
                    provider="kubanfy",
                    provider_track_id=str(track.id),
                    track_id=track.id,
                    title=track.title,
                    artists=[artist.name for artist in artist_rows],
                    album=release.title if release else None,
                    duration=track.duration,
                    artwork=track.artwork_url,
                    isrc=track.isrc,
                )
            )

    return results[:limit]


@router.get("/local-delivery/{token}")
async def local_storage_delivery(token: str):
    """Deliver a signed staging-local KBY object over HTTPS.

    Authorization has already happened before the URL is issued. The token
    authenticates only this exact stored KBY object until its expiry.
    """
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status_code=404, detail="Local delivery is unavailable")
    bucket, key, _ = storage.verify_delivery_token(token)
    total = await storage.size(key, bucket=bucket)
    return StreamingResponse(
        storage.stream(key, bucket=bucket, chunk_size=65536),
        media_type="application/vnd.kubanfy.kby",
        headers={
            "Content-Length": str(total),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

@router.get("/content/{track_id}")
async def music_content_stream(
    track_id: UUID,
    request: Request,
    session: DbSession,
    user: CurrentUser,
    quality: str = Query("low"),
):
    """Stream audio with HTTP Range (resume). Uses cache object when available."""
    raise HTTPException(status_code=410, detail="Raw KBY streaming is disabled; use authorized playback delivery")
    from fastapi.responses import Response, StreamingResponse

    from app.core.exceptions import ValidationError
    from app.services.http_range import parse_bytes_range
    from app.storage import get_storage

    async def storage_range_stream(storage, key, start, end, bucket):
        yield await storage.get_range(
            key,
            start,
            end,
            bucket=bucket,
        )

    geo = GeoService()
    ip = request.client.host if request.client else None
    real_ip = geo.resolve_client_ip(ip, forwarded_for=request.headers.get("x-forwarded-for"))
    await AntiAbuseService().check_download(str(user.id), real_ip)
    entitlement = EntitlementService(session)
    await entitlement.require_track_access(user.id, track_id)
    await entitlement.require_quality_access(user.id, quality)
    engine = MusicEngine(session, provider_manager=_manager)
    result = await engine.download_by_track_id(track_id=track_id, quality=quality)

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
