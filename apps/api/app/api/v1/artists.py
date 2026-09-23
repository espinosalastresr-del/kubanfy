"""Artist portal API and public artist catalog."""

from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from typing import Annotated
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.artist_member import ArtistMember, ArtistMemberRole
from app.models.user import User
from app.models.music import Artist, AudioAsset, Release, Track, TrackArtist, TrackStatus
from app.schemas.artist import (
    ArtistCreateRequest,
    ArtistUpdateRequest,
    ArtistResponse,
    PublicReleaseResponse,
    PublicTrackResponse,
    PublishTrackResponse,
    TrackUploadResponse,
)
from app.schemas.catalog import (
    ReleaseCreateRequest,
    ReleaseResponse,
    ReleaseUpdateRequest,
    ReleaseScheduleRequest,
    TrackStatusResponse,
    TrackUpdateRequest,
)
from app.services.artist_upload import ArtistUploadService
from app.services.release_track import ReleaseTrackService
from app.services.rights_royalty import RightsRoyaltyService
from app.schemas.rights import CollaboratorSplitsRequest, CollaboratorSplitResponse, RoyaltyLedgerRequest, RoyaltyLedgerResponse, RoyaltySettlementRequest, RoyaltySettlementResponse

router = APIRouter(prefix="/artist", tags=["artist"])


def _slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:200] or "artist"


@router.post("", response_model=ArtistResponse, status_code=201)
async def create_artist(body: ArtistCreateRequest, user: CurrentUser, session: DbSession) -> ArtistResponse:
    slug = _slugify(body.name)
    existing = await session.scalar(select(Artist).where(Artist.slug == slug))
    if existing:
        raise ConflictError("Artist slug already exists")
    artist = Artist(
        name=body.name.strip(), slug=slug, bio=body.bio,
        country=body.country.upper(), status="active", verified=False,
    )
    session.add(artist)
    await session.flush()
    session.add(ArtistMember(artist_id=artist.id, user_id=user.id, role=ArtistMemberRole.OWNER))
    await session.flush()
    return ArtistResponse.model_validate(artist)


@router.get("/mine", response_model=list[ArtistResponse])
async def my_artists(user: CurrentUser, session: DbSession) -> list[ArtistResponse]:
    result = await session.execute(
        select(Artist).join(ArtistMember, ArtistMember.artist_id == Artist.id)
        .where(ArtistMember.user_id == user.id).order_by(Artist.name)
    )
    return [ArtistResponse.model_validate(a) for a in result.scalars().all()]


@router.patch("/{artist_id}", response_model=ArtistResponse)
async def update_artist(artist_id: UUID, body: ArtistUpdateRequest, user: CurrentUser, session: DbSession) -> ArtistResponse:
    artist = await session.get(Artist, artist_id)
    if artist is None:
        raise NotFoundError("Artist not found")
    member = await session.scalar(select(ArtistMember).where(
        ArtistMember.artist_id == artist_id, ArtistMember.user_id == user.id,
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


# ---------- Artist-owned release / track management ----------

@router.post("/{artist_id}/releases", response_model=ReleaseResponse, status_code=201)
async def create_release(artist_id: UUID, body: ReleaseCreateRequest, user: CurrentUser, session: DbSession) -> ReleaseResponse:
    release = await ReleaseTrackService(session).create_release(
        user_id=user.id, artist_id=artist_id, title=body.title, type=body.type,
        description=body.description, artwork_asset=body.artwork_asset, release_date=body.release_date,
    )
    return ReleaseResponse.model_validate(release)


@router.patch("/{artist_id}/releases/{release_id}", response_model=ReleaseResponse)
async def update_release(artist_id: UUID, release_id: UUID, body: ReleaseUpdateRequest, user: CurrentUser, session: DbSession) -> ReleaseResponse:
    release = await ReleaseTrackService(session).update_release(
        user_id=user.id, artist_id=artist_id, release_id=release_id, title=body.title, type=body.type,
        description=body.description, artwork_asset=body.artwork_asset, release_date=body.release_date,
    )
    return ReleaseResponse.model_validate(release)


@router.post("/{artist_id}/releases/{release_id}/schedule", response_model=ReleaseResponse)
async def schedule_release(
    artist_id: UUID,
    release_id: UUID,
    body: ReleaseScheduleRequest,
    user: CurrentUser,
    session: DbSession,
) -> ReleaseResponse:
    release = await ReleaseTrackService(session).schedule_release(
        user_id=user.id,
        artist_id=artist_id,
        release_id=release_id,
        publish_at=body.publish_at,
        unpublish_at=body.unpublish_at,
    )
    return ReleaseResponse.model_validate(release)


@router.post("/{artist_id}/releases/{release_id}/publish", response_model=ReleaseResponse)
async def publish_release(artist_id: UUID, release_id: UUID, user: CurrentUser, session: DbSession) -> ReleaseResponse:
    release = await ReleaseTrackService(session).set_release_status(
        user_id=user.id, artist_id=artist_id, release_id=release_id, status=TrackStatus.PUBLISHED,
    )
    return ReleaseResponse.model_validate(release)


@router.post("/{artist_id}/releases/{release_id}/hide", response_model=ReleaseResponse)
async def hide_release(artist_id: UUID, release_id: UUID, user: CurrentUser, session: DbSession) -> ReleaseResponse:
    release = await ReleaseTrackService(session).set_release_status(
        user_id=user.id, artist_id=artist_id, release_id=release_id, status=TrackStatus.HIDDEN,
    )
    return ReleaseResponse.model_validate(release)


@router.post("/{artist_id}/releases/{release_id}/takedown", response_model=ReleaseResponse)
async def takedown_release(artist_id: UUID, release_id: UUID, user: CurrentUser, session: DbSession) -> ReleaseResponse:
    release = await ReleaseTrackService(session).set_release_status(
        user_id=user.id, artist_id=artist_id, release_id=release_id, status=TrackStatus.TAKEDOWN,
    )
    return ReleaseResponse.model_validate(release)


@router.post("/{artist_id}/releases/{release_id}/restore", response_model=ReleaseResponse)
async def restore_release(artist_id: UUID, release_id: UUID, user: CurrentUser, session: DbSession) -> ReleaseResponse:
    release = await ReleaseTrackService(session).set_release_status(
        user_id=user.id, artist_id=artist_id, release_id=release_id, status=TrackStatus.DRAFT,
    )
    return ReleaseResponse.model_validate(release)


@router.delete("/{artist_id}/releases/{release_id}", response_model=ReleaseResponse)
async def delete_release(artist_id: UUID, release_id: UUID, user: CurrentUser, session: DbSession) -> ReleaseResponse:
    release = await ReleaseTrackService(session).set_release_status(
        user_id=user.id, artist_id=artist_id, release_id=release_id, status=TrackStatus.DELETED,
    )
    return ReleaseResponse.model_validate(release)


@router.patch("/{artist_id}/tracks/{track_id}", response_model=TrackUploadResponse)
async def update_track(artist_id: UUID, track_id: UUID, body: TrackUpdateRequest, user: CurrentUser, session: DbSession) -> TrackUploadResponse:
    track = await ReleaseTrackService(session).update_track(
        user_id=user.id, artist_id=artist_id, track_id=track_id, title=body.title, isrc=body.isrc,
        explicit=body.explicit, language=body.language, release_date=body.release_date,
        artwork_url=body.artwork_url, release_id=body.release_id,
    )
    asset = await session.scalar(select(AudioAsset).where(
        AudioAsset.track_id == track.id,
        AudioAsset.is_active.is_(True),
    ).order_by(AudioAsset.created_at.desc()).limit(1))
    return TrackUploadResponse(
        track_id=track.id, status=track.status.value,
        master_storage_key=asset.storage_key if asset else "",
        content_hash=asset.content_hash if asset else "",
        duration=track.duration, job_id=None,
    )


@router.post("/{artist_id}/tracks/{track_id}/replace-audio", response_model=TrackUploadResponse)
async def replace_track_audio(
    artist_id: UUID, track_id: UUID, user: CurrentUser, session: DbSession,
    file: UploadFile = File(...), accept_license: bool = Form(True),
) -> TrackUploadResponse:
    if not file.filename:
        raise ValidationError("Filename required")
    data = await file.read()
    if not data:
        raise ValidationError("Empty file")
    result = await ArtistUploadService(session).replace_track_audio(
        user_id=user.id, artist_id=artist_id, track_id=track_id,
        file_bytes=data, filename=file.filename, accept_license=accept_license,
    )
    return TrackUploadResponse(
        track_id=result.track_id, status=result.status,
        master_storage_key=result.master_storage_key,
        content_hash=result.content_hash, duration=result.duration, job_id=result.job_id,
    )


@router.post("/{artist_id}/tracks/{track_id}/publish", response_model=TrackStatusResponse)
async def publish_track(artist_id: UUID, track_id: UUID, user: CurrentUser, session: DbSession) -> TrackStatusResponse:
    track = await ArtistUploadService(session).publish_track(user_id=user.id, track_id=track_id, artist_id=artist_id)
    return TrackStatusResponse(track_id=track.id, status=track.status)


@router.post("/{artist_id}/tracks/{track_id}/hide", response_model=TrackStatusResponse)
async def hide_track(artist_id: UUID, track_id: UUID, user: CurrentUser, session: DbSession) -> TrackStatusResponse:
    track = await ReleaseTrackService(session).set_track_status(
        user_id=user.id, artist_id=artist_id, track_id=track_id, status=TrackStatus.HIDDEN,
    )
    return TrackStatusResponse(track_id=track.id, status=track.status)


@router.post("/{artist_id}/tracks/{track_id}/takedown", response_model=TrackStatusResponse)
async def takedown_track(artist_id: UUID, track_id: UUID, user: CurrentUser, session: DbSession) -> TrackStatusResponse:
    track = await ReleaseTrackService(session).set_track_status(
        user_id=user.id, artist_id=artist_id, track_id=track_id, status=TrackStatus.TAKEDOWN,
    )
    return TrackStatusResponse(track_id=track.id, status=track.status)


@router.post("/{artist_id}/tracks/{track_id}/restore", response_model=TrackStatusResponse)
async def restore_track(artist_id: UUID, track_id: UUID, user: CurrentUser, session: DbSession) -> TrackStatusResponse:
    track = await ReleaseTrackService(session).set_track_status(
        user_id=user.id, artist_id=artist_id, track_id=track_id, status=TrackStatus.DRAFT,
    )
    return TrackStatusResponse(track_id=track.id, status=track.status)


@router.delete("/{artist_id}/tracks/{track_id}", response_model=TrackStatusResponse)
async def delete_track(artist_id: UUID, track_id: UUID, user: CurrentUser, session: DbSession) -> TrackStatusResponse:
    track = await ReleaseTrackService(session).set_track_status(
        user_id=user.id, artist_id=artist_id, track_id=track_id, status=TrackStatus.DELETED,
    )
    return TrackStatusResponse(track_id=track.id, status=track.status)


@router.put("/{artist_id}/rights/splits", response_model=list[CollaboratorSplitResponse])
async def replace_rights_splits(
    artist_id: UUID, body: CollaboratorSplitsRequest, user: CurrentUser, session: DbSession
) -> list[CollaboratorSplitResponse]:
    if body.scope_type.lower() not in ("track", "release"):
        raise ValidationError("scope_type must be track or release")
    rows = await RightsRoyaltyService(session).set_splits(
        user_id=user.id, artist_id=artist_id, scope_type=body.scope_type,
        scope_id=body.scope_id, splits=[x.model_dump() for x in body.splits],
    )
    return [CollaboratorSplitResponse.model_validate(x) for x in rows]


@router.get("/{artist_id}/rights/splits", response_model=list[CollaboratorSplitResponse])
async def get_rights_splits(
    artist_id: UUID, scope_type: str, scope_id: UUID, user: CurrentUser, session: DbSession
) -> list[CollaboratorSplitResponse]:
    rows = await RightsRoyaltyService(session).get_splits(user_id=user.id, artist_id=artist_id, scope_type=scope_type, scope_id=scope_id)
    return [CollaboratorSplitResponse.model_validate(x) for x in rows]


@router.post("/{artist_id}/royalties/ledger", response_model=RoyaltyLedgerResponse, status_code=201)
async def append_royalty_ledger(
    artist_id: UUID,
    body: RoyaltyLedgerRequest,
    user: Annotated[User, Depends(require_permissions("royalties.write"))],
    session: DbSession,
) -> RoyaltyLedgerResponse:
    row = await RightsRoyaltyService(session).append_ledger(
        user_id=user.id, artist_id=artist_id, amount_cents=body.amount_cents, source_type=body.source_type,
        idempotency_key=body.idempotency_key, direction=body.direction,
        source_id=body.source_id, currency=body.currency, metadata=body.metadata,
    )
    return RoyaltyLedgerResponse.model_validate(row)


@router.post("/{artist_id}/royalties/settlements", response_model=RoyaltySettlementResponse, status_code=201)
async def create_royalty_settlement(
    artist_id: UUID,
    body: RoyaltySettlementRequest,
    user: Annotated[User, Depends(require_permissions("royalties.write"))],
    session: DbSession,
) -> RoyaltySettlementResponse:
    service = RightsRoyaltyService(session)
    await service._authorized(user.id, artist_id)
    row = await service.create_settlement(
        artist_id=artist_id,
        period_start=body.period_start,
        period_end=body.period_end,
        gross_cents=body.gross_cents,
        net_cents=body.net_cents,
        idempotency_key=body.idempotency_key,
        currency=body.currency,
    )
    return RoyaltySettlementResponse.model_validate(row)


@router.post("/{artist_id}/royalties/settlements/{settlement_id}/approve", response_model=RoyaltySettlementResponse)
async def approve_royalty_settlement(
    artist_id: UUID,
    settlement_id: UUID,
    user: Annotated[User, Depends(require_permissions("royalties.write"))],
    session: DbSession,
) -> RoyaltySettlementResponse:
    row = await RightsRoyaltyService(session).approve_settlement(user_id=user.id, settlement_id=settlement_id)
    account = await session.get(__import__("app.models.rights", fromlist=["RoyaltyAccount"]).RoyaltyAccount, row.account_id)
    if account is None or account.artist_id != artist_id:
        raise NotFoundError("Settlement not found")
    return RoyaltySettlementResponse.model_validate(row)


@router.post("/{artist_id}/royalties/settlements/{settlement_id}/pay", response_model=RoyaltySettlementResponse)
async def pay_royalty_settlement(
    artist_id: UUID,
    settlement_id: UUID,
    user: Annotated[User, Depends(require_permissions("royalties.write"))],
    session: DbSession,
) -> RoyaltySettlementResponse:
    row = await RightsRoyaltyService(session).mark_settlement_paid(user_id=user.id, settlement_id=settlement_id)
    account = await session.get(__import__("app.models.rights", fromlist=["RoyaltyAccount"]).RoyaltyAccount, row.account_id)
    if account is None or account.artist_id != artist_id:
        raise NotFoundError("Settlement not found")
    return RoyaltySettlementResponse.model_validate(row)


@router.post("/{artist_id}/royalties/settlements/{settlement_id}/reject", response_model=RoyaltySettlementResponse)
async def reject_royalty_settlement(
    artist_id: UUID,
    settlement_id: UUID,
    user: Annotated[User, Depends(require_permissions("royalties.write"))],
    session: DbSession,
) -> RoyaltySettlementResponse:
    row = await RightsRoyaltyService(session).reject_settlement(user_id=user.id, settlement_id=settlement_id)
    account = await session.get(__import__("app.models.rights", fromlist=["RoyaltyAccount"]).RoyaltyAccount, row.account_id)
    if account is None or account.artist_id != artist_id:
        raise NotFoundError("Settlement not found")
    return RoyaltySettlementResponse.model_validate(row)


@router.get("/{artist_id}", response_model=ArtistResponse)
async def get_artist(artist_id: UUID, session: DbSession) -> ArtistResponse:
    artist = await session.get(Artist, artist_id)
    if artist is None or artist.status != "active":
        raise NotFoundError("Artist not found")
    return ArtistResponse.model_validate(artist)


@router.get("/{artist_id}/releases", response_model=list[PublicReleaseResponse])
async def artist_releases(artist_id: UUID, session: DbSession) -> list[PublicReleaseResponse]:
    artist = await session.get(Artist, artist_id)
    if artist is None or artist.status != "active":
        raise NotFoundError("Artist not found")
    result = await session.execute(
        select(Release).where(Release.artist_id == artist_id, Release.status == TrackStatus.PUBLISHED)
        .order_by(Release.release_date.desc().nullslast(), Release.created_at.desc())
    )
    return [PublicReleaseResponse(
        id=r.id, title=r.title, type=r.type.value, artwork_asset=r.artwork_asset,
        release_date=r.release_date, status=r.status.value,
    ) for r in result.scalars().all()]


@router.get("/{artist_id}/tracks", response_model=list[PublicTrackResponse])
async def artist_tracks(artist_id: UUID, session: DbSession) -> list[PublicTrackResponse]:
    artist = await session.get(Artist, artist_id)
    if artist is None or artist.status != "active":
        raise NotFoundError("Artist not found")
    result = await session.execute(
        select(Track, Release)
        .join(TrackArtist, TrackArtist.track_id == Track.id)
        .outerjoin(Release, Release.id == Track.release_id)
        .where(TrackArtist.artist_id == artist_id, Track.status == TrackStatus.PUBLISHED)
        .order_by(Track.release_date.desc().nullslast(), Track.created_at.desc())
    )
    return [PublicTrackResponse(
        id=t.id, title=t.title, slug=t.slug, duration=t.duration, explicit=t.explicit,
        language=t.language, release_id=r.id if r else None, release_title=r.title if r else None,
    ) for t, r in result.all()]


@router.post("/{artist_id}/tracks/upload", response_model=TrackUploadResponse, status_code=201)
async def upload_track(
    artist_id: UUID, user: CurrentUser, session: DbSession,
    title: str = Form(...), accept_license: bool = Form(...), explicit: bool = Form(False),
    language: str = Form("es"), file: UploadFile = File(...),
) -> TrackUploadResponse:
    if not file.filename:
        raise ValidationError("Filename required")
    data = await file.read()
    if not data:
        raise ValidationError("Empty file")
    result = await ArtistUploadService(session).upload_track(
        user_id=user.id, artist_id=artist_id, title=title, file_bytes=data,
        filename=file.filename, accept_license=accept_license, explicit=explicit, language=language,
    )
    return TrackUploadResponse(
        track_id=result.track_id, status=result.status, master_storage_key=result.master_storage_key,
        content_hash=result.content_hash, duration=result.duration, job_id=result.job_id,
    )
