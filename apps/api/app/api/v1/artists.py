"""Artist portal API: create artist, upload track, publish."""

from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import ConflictError, ValidationError
from app.models.artist_member import ArtistMember, ArtistMemberRole
from app.models.music import Artist
from app.schemas.artist import (
    ArtistCreateRequest,
    ArtistResponse,
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
