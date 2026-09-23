"""Artist portal API and public artist catalog."""

from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.artist_member import ArtistMember, ArtistMemberRole
from app.models.music import Artist, Release, Track, TrackArtist, TrackStatus
from app.schemas.artist import (
    ArtistCreateRequest,
    ArtistResponse,
    PublicReleaseResponse,
    PublicTrackResponse,
    PublishTrackResponse,
    TrackUploadResponse,
)
from app.services.artist_upload import ArtistUploadService

router = APIRouter(prefix="/artist", tags=["artist"])


def _slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:200] or "artist"


@router.post("", response_model=ArtistResponse, status_code=201)
async def create_artist(
    body: ArtistCreateRequest,
    user: CurrentUser,
    session: DbSession,
) -> ArtistResponse:
    slug = _slugify(body.name)
    existing = await session.scalar(select(Artist).where(Artist.slug == slug))
    if existing:
        raise ConflictError("Artist slug already exists")

    artist = Artist(
        name=body.name.strip(),
        slug=slug,
        bio=body.bio,
        country=body.country.upper(),
        status="active",
        verified=False,
    )
    session.add(artist)
    await session.flush()
    session.add(
        ArtistMember(
            artist_id=artist.id,
            user_id=user.id,
            role=ArtistMemberRole.OWNER,
        )
    )
    await session.flush()
    return ArtistResponse.model_validate(artist)


@router.get("/mine", response_model=list[ArtistResponse])
async def my_artists(user: CurrentUser, session: DbSession) -> list[ArtistResponse]:
    result = await session.execute(
        select(Artist)
        .join(ArtistMember, ArtistMember.artist_id == Artist.id)
        .where(ArtistMember.user_id == user.id)
        .order_by(Artist.name)
    )
    return [ArtistResponse.model_validate(a) for a in result.scalars().all()]




@router.patch("/{artist_id}", response_model=ArtistResponse)
async def update_artist(
    artist_id: UUID,
    body: ArtistCreateRequest,
    user: CurrentUser,
    session: DbSession,
) -> ArtistResponse:
    artist = await session.get(Artist, artist_id)
    if artist is None:
        raise NotFoundError("Artist not found")
    member = await session.scalar(select(ArtistMember).where(
        ArtistMember.artist_id == artist_id,
        ArtistMember.user_id == user.id,
    ))
    if member is None or member.role not in (ArtistMemberRole.OWNER, ArtistMemberRole.MANAGER):
        raise NotFoundError("Artist not found")
    artist.name = body.name.strip()
    artist.bio = body.bio
    artist.country = body.country.upper()
    new_slug = _slugify(artist.name)
    if new_slug != artist.slug:
        conflict = await session.scalar(select(Artist).where(Artist.slug == new_slug, Artist.id != artist.id))
        if conflict:
            raise ConflictError("Artist slug already exists")
        artist.slug = new_slug
    await session.flush()
    return ArtistResponse.model_validate(artist)


@router.get("/{artist_id}", response_model=ArtistResponse)
async def get_artist(artist_id: UUID, session: DbSession) -> ArtistResponse:
    artist = await session.get(Artist, artist_id)
    if artist is None or artist.status != "active":
        raise NotFoundError("Artist not found")
    return ArtistResponse.model_validate(artist)


@router.get("/{artist_id}/releases", response_model=list[PublicReleaseResponse])
async def artist_releases(
    artist_id: UUID,
    session: DbSession,
) -> list[PublicReleaseResponse]:
    artist = await session.get(Artist, artist_id)
    if artist is None or artist.status != "active":
        raise NotFoundError("Artist not found")

    result = await session.execute(
        select(Release)
        .where(
            Release.artist_id == artist_id,
            Release.status == TrackStatus.PUBLISHED,
        )
        .order_by(Release.release_date.desc().nullslast(), Release.created_at.desc())
    )
    return [
        PublicReleaseResponse(
            id=release.id,
            title=release.title,
            type=release.type.value,
            artwork_asset=release.artwork_asset,
            release_date=release.release_date,
            status=release.status.value,
        )
        for release in result.scalars().all()
    ]


@router.get("/{artist_id}/tracks", response_model=list[PublicTrackResponse])
async def artist_tracks(
    artist_id: UUID,
    session: DbSession,
) -> list[PublicTrackResponse]:
    artist = await session.get(Artist, artist_id)
    if artist is None or artist.status != "active":
        raise NotFoundError("Artist not found")

    result = await session.execute(
        select(Track, Release)
        .join(TrackArtist, TrackArtist.track_id == Track.id)
        .outerjoin(Release, Release.id == Track.release_id)
        .where(
            TrackArtist.artist_id == artist_id,
            Track.status == TrackStatus.PUBLISHED,
        )
        .order_by(Track.release_date.desc().nullslast(), Track.created_at.desc())
    )
    return [
        PublicTrackResponse(
            id=track.id,
            title=track.title,
            slug=track.slug,
            duration=track.duration,
            explicit=track.explicit,
            language=track.language,
            release_id=release.id if release else None,
            release_title=release.title if release else None,
        )
        for track, release in result.all()
    ]


@router.post("/{artist_id}/tracks/upload", response_model=TrackUploadResponse, status_code=201)
async def upload_track(
    artist_id: UUID,
    user: CurrentUser,
    session: DbSession,
    title: str = Form(...),
    accept_license: bool = Form(...),
    explicit: bool = Form(False),
    language: str = Form("es"),
    file: UploadFile = File(...),
) -> TrackUploadResponse:
    if not file.filename:
        raise ValidationError("Filename required")
    data = await file.read()
    if not data:
        raise ValidationError("Empty file")

    svc = ArtistUploadService(session)
    result = await svc.upload_track(
        user_id=user.id,
        artist_id=artist_id,
        title=title,
        file_bytes=data,
        filename=file.filename,
        accept_license=accept_license,
        explicit=explicit,
        language=language,
    )
    return TrackUploadResponse(
        track_id=result.track_id,
        status=result.status,
        master_storage_key=result.master_storage_key,
        content_hash=result.content_hash,
        duration=result.duration,
        job_id=result.job_id,
    )


@router.post("/{artist_id}/tracks/{track_id}/publish", response_model=PublishTrackResponse)
async def publish_track(
    artist_id: UUID,
    track_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> PublishTrackResponse:
    svc = ArtistUploadService(session)
    track = await svc.publish_track(user_id=user.id, track_id=track_id, artist_id=artist_id)
    return PublishTrackResponse(track_id=track.id, status=track.status.value)
