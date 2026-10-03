"""Music Engine API endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.core.exceptions import AuthError
from app.core.logging import get_logger
from app.providers.registry import ProviderManager, create_default_registry
from app.schemas.music import (
    MusicDownloadRequest,
    MusicDownloadResponse,
    MusicPreviewRequest,
    MusicPreviewResponse,
    MusicPlaybackResponse,
    MusicOfflineBootstrapResponse,
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
from app.models.music import Artist, AudioAsset, AudioQuality, Release, Track, TrackArtist
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
logger = get_logger(__name__)


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
    started = time.perf_counter()
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "playback_authorization_started",
        category="playback.authorize",
        request_id=request_id,
        track_id=str(track_id),
        quality=quality,
        user_id=str(user.id),
    )
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
        logger.error(
            "playback_authorization_missing_url",
            category="playback.authorize",
            request_id=request_id,
            track_id=str(track_id),
            quality=quality,
            user_id=str(user.id),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Playable audio URL unavailable")
    logger.info(
        "playback_authorization_succeeded",
        category="playback.authorize",
        request_id=request_id,
        track_id=str(track_id),
        quality=result.quality,
        storage_bucket=result.storage_bucket.value,
        content_hash=result.content_hash,
        storage_key_present=bool(result.storage_key),
        signed_url_expires_in=result.signed_url.expires_in_seconds,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        user_id=str(user.id),
    )
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


@router.get("/offline/bootstrap", response_model=list[MusicOfflineBootstrapResponse])
async def music_offline_bootstrap(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    limit: int = Query(3, ge=1, le=3),
) -> list[MusicOfflineBootstrapResponse]:
    """Issue up to three free, device-bound offline bootstrap assets.

    This is distinct from Premium persistent downloads. It authorizes only the
    small offline-first bootstrap set and still uses the normal published-track,
    entitlement, KBY, storage, and device-binding pipeline.
    """
    started = time.perf_counter()
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "offline_bootstrap_started",
        category="offline.bootstrap",
        request_id=request_id,
        user_id=str(user.id),
        limit=limit,
        device_id_present=bool(request.headers.get("X-Device-ID", "").strip()),
    )
    device_id = request.headers.get("X-Device-ID", "").strip()
    if not device_id:
        from app.core.exceptions import ValidationError

        raise ValidationError("X-Device-ID is required for offline bootstrap")

    geo = GeoService()
    ip = request.client.host if request.client else None
    real_ip = geo.resolve_client_ip(
        ip,
        forwarded_for=request.headers.get("x-forwarded-for"),
    )
    await AntiAbuseService().check_download(str(user.id), real_ip)

    asset_exists = select(AudioAsset.track_id).where(
        AudioAsset.track_id == Track.id,
        AudioAsset.quality == AudioQuality.LOW,
        AudioAsset.is_active.is_(True),
        AudioAsset.content_hash.is_not(None),
        AudioAsset.storage_key.is_not(None),
    )
    tracks = (
        await session.scalars(
            select(Track)
            .where(
                Track.status == "published",
                asset_exists.exists(),
            )
            .order_by(Track.created_at, Track.id)
            .limit(limit)
        )
    ).all()

    logger.info(
        "offline_bootstrap_tracks_selected",
        category="offline.bootstrap",
        request_id=request_id,
        user_id=str(user.id),
        selected_count=len(tracks),
        track_ids=[str(track.id) for track in tracks],
    )
    if not tracks:
        logger.warning(
            "offline_bootstrap_no_tracks",
            category="offline.bootstrap",
            request_id=request_id,
            user_id=str(user.id),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return []

    entitlement = EntitlementService(session)
    engine = MusicEngine(session, provider_manager=_manager)
    license_service = OfflineLicenseService(session)
    response: list[MusicOfflineBootstrapResponse] = []

    for track in tracks:
        track_started = time.perf_counter()
        try:
            logger.info(
                "offline_bootstrap_track_started",
                category="offline.bootstrap",
                request_id=request_id,
                user_id=str(user.id),
                track_id=str(track.id),
            )
            await entitlement.require_track_access(user.id, track.id)
            playback = await engine.download_by_track_id(
            track_id=track.id,
            quality="low",
            user_id=user.id,
        )
            if (
                playback.signed_url is None
                or playback.content_hash is None
                or not playback.kby_key
            ):
                logger.warning(
                    "offline_bootstrap_track_incomplete",
                    category="offline.bootstrap",
                    request_id=request_id,
                    user_id=str(user.id),
                    track_id=str(track.id),
                    signed_url_present=playback.signed_url is not None,
                    content_hash_present=playback.content_hash is not None,
                    kby_key_present=bool(playback.kby_key),
                )
                continue

        asset = await session.scalar(
            select(AudioAsset)
            .where(
                AudioAsset.track_id == track.id,
                AudioAsset.quality == AudioQuality.LOW,
                AudioAsset.is_active.is_(True),
                AudioAsset.content_hash == playback.content_hash,
                AudioAsset.storage_key.is_not(None),
            )
            .order_by(AudioAsset.version.desc())
        )
            if asset is None:
                logger.warning(
                    "offline_bootstrap_asset_missing",
                    category="offline.bootstrap",
                    request_id=request_id,
                    user_id=str(user.id),
                    track_id=str(track.id),
                    content_hash=playback.content_hash,
                )
                continue

            license_row, offline_license = await license_service.issue_bootstrap(
            user_id=user.id,
            device_id=device_id,
            track_id=track.id,
            quality="low",
        )
            response.append(
                MusicOfflineBootstrapResponse(
                    track_id=track.id,
                    title=track.title,
                    duration=track.duration,
                    url=playback.signed_url.url,
                    expires_in_seconds=playback.signed_url.expires_in_seconds,
                    quality="low",
                    content_hash=playback.content_hash,
                    kby_key=playback.kby_key,
                    asset_version=asset.version,
                    offline_license=offline_license,
                    offline_license_expires_at=license_row.expires_at.isoformat(),
                )
            )
            logger.info(
                "offline_bootstrap_track_succeeded",
                category="offline.bootstrap",
                request_id=request_id,
                user_id=str(user.id),
                track_id=str(track.id),
                asset_version=asset.version,
                content_hash=playback.content_hash,
                elapsed_ms=round((time.perf_counter() - track_started) * 1000, 2),
            )
        except Exception as exc:
            logger.exception(
                "offline_bootstrap_track_failed",
                category="offline.bootstrap",
                request_id=request_id,
                user_id=str(user.id),
                track_id=str(track.id),
                elapsed_ms=round((time.perf_counter() - track_started) * 1000, 2),
                error_type=type(exc).__name__,
                error=str(exc)[:500],
            )

    logger.info(
        "offline_bootstrap_completed",
        category="offline.bootstrap",
        request_id=request_id,
        user_id=str(user.id),
        requested_limit=limit,
        returned_count=len(response),
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return response


@router.get("/search", response_model=list[TrackSearchResult])
async def music_search(
    request: Request,
    session: DbSession,
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=50),
) -> list[TrackSearchResult]:
    geo = GeoService()
    ip = request.client.host if request.client else None
    real_ip = geo.resolve_client_ip(
        ip,
        forwarded_for=request.headers.get("x-forwarded-for"),
    )
    await AntiAbuseService().check_search(real_ip)

    normalized = q.strip()
    pattern = f"%{normalized.lower()}%"

    # First-party catalog results come first so every owned track has a stable
    # KubanFy track_id and can open the native detail screen.
    local_rows = (
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
            .order_by(Track.title, Track.id)
            .limit(limit)
        )
    ).all()

    results: list[TrackSearchResult] = []
    local_keys: set[str] = set()
    local_isrcs: set[str] = set()

    for track, release in local_rows:
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
        artists = [artist.name for artist in artist_rows]
        key = (
            f"{track.title.casefold()}|"
            f"{'|'.join(name.casefold() for name in artists)}"
        )
        local_keys.add(key)
        if track.isrc:
            local_isrcs.add(track.isrc.casefold())
        results.append(
            TrackSearchResult(
                provider="kubanfy",
                provider_track_id=str(track.id),
                track_id=track.id,
                title=track.title,
                artists=artists,
                album=release.title if release else None,
                duration=track.duration,
                artwork=track.artwork_url,
                isrc=track.isrc,
            )
        )

    remaining = max(0, limit - len(results))
    if remaining:
        provider_results = await _manager.search(normalized, limit=limit)
        for name, meta in provider_results:
            provider_isrc = meta.isrc.casefold() if meta.isrc else None
            provider_artists = [artist.casefold() for artist in meta.artists]
            provider_key = (
                f"{meta.title.casefold()}|"
                f"{'|'.join(provider_artists)}"
            )
            if provider_isrc and provider_isrc in local_isrcs:
                continue
            if provider_key in local_keys:
                continue

            matched_track_id: UUID | None = None
            if provider_isrc:
                matched_track_id = await session.scalar(
                    select(Track.id).where(
                        Track.status == "published",
                        Track.isrc.is_not(None),
                        func.lower(Track.isrc) == provider_isrc,
                    )
                )
            if matched_track_id is None:
                matched_track_id = await session.scalar(
                    select(Track.id)
                    .join(
                        TrackArtist,
                        TrackArtist.track_id == Track.id,
                    )
                    .join(
                        Artist,
                        Artist.id == TrackArtist.artist_id,
                    )
                    .where(
                        Track.status == "published",
                        func.lower(Track.title) == meta.title.casefold(),
                        Artist.status == "active",
                        func.lower(Artist.name).in_(provider_artists),
                    )
                )

            results.append(
                TrackSearchResult(
                    provider=name,
                    provider_track_id=meta.provider_track_id,
                    track_id=matched_track_id,
                    title=meta.title,
                    artists=list(meta.artists),
                    album=meta.album,
                    duration=meta.duration_seconds,
                    artwork=meta.artwork_url,
                    isrc=meta.isrc,
                )
            )
            if len(results) >= limit:
                break

    return results[:limit]


@router.get("/local-delivery/{token}")
async def local_storage_delivery(request: Request, token: str):
    """Deliver a signed staging-local KBY object over HTTPS."""
    started = time.perf_counter()
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "local_delivery_started",
        category="playback.delivery",
        request_id=request_id,
        token_length=len(token),
    )
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        logger.error(
            "local_delivery_backend_unavailable",
            category="playback.delivery",
            request_id=request_id,
            backend=type(storage).__name__,
        )
        raise HTTPException(status_code=404, detail="Local delivery is unavailable")

    bucket, key, expires_at = storage.verify_delivery_token(token)
    key_fingerprint = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    total = await storage.size(key, bucket=bucket)
    logger.info(
        "local_delivery_authorized",
        category="playback.delivery",
        request_id=request_id,
        bucket=bucket.value,
        key_fingerprint=key_fingerprint,
        file_size_bytes=total,
        expires_at=expires_at,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    )

    async def delivery_stream():
        stream_started = time.perf_counter()
        bytes_seen = 0
        chunks = 0
        try:
            async for chunk in storage.stream(key, bucket=bucket, chunk_size=65536):
                chunks += 1
                bytes_seen += len(chunk)
                yield chunk
        except asyncio.CancelledError:
            logger.warning(
                "local_delivery_cancelled",
                category="playback.delivery",
                request_id=request_id,
                bucket=bucket.value,
                key_fingerprint=key_fingerprint,
                chunks=chunks,
                bytes_sent=bytes_seen,
                elapsed_ms=round((time.perf_counter() - stream_started) * 1000, 2),
            )
            raise
        except Exception as exc:
            logger.exception(
                "local_delivery_stream_failed",
                category="playback.delivery",
                request_id=request_id,
                bucket=bucket.value,
                key_fingerprint=key_fingerprint,
                chunks=chunks,
                bytes_sent=bytes_seen,
                elapsed_ms=round((time.perf_counter() - stream_started) * 1000, 2),
                error_type=type(exc).__name__,
                error=str(exc)[:500],
            )
            raise
        else:
            logger.info(
                "local_delivery_completed",
                category="playback.delivery",
                request_id=request_id,
                bucket=bucket.value,
                key_fingerprint=key_fingerprint,
                chunks=chunks,
                bytes_sent=bytes_seen,
                elapsed_ms=round((time.perf_counter() - stream_started) * 1000, 2),
            )

    return StreamingResponse(
        delivery_stream(),
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
