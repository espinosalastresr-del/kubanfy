"""Admin control plane — protected by RBAC permissions."""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession, require_permissions
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.admin import ModerationReportType, ModerationStatus
from app.models.artist_member import ArtistMember, ArtistMemberRole
from app.models.music import Artist, AudioAsset, Track, TrackArtist, TrackStatus
from app.models.user import User
from app.schemas.catalog import TrackUpdateRequest
from app.services.admin import AdminService
from app.services.artist_upload import ArtistUploadService
from app.services.rbac import RbacService
from app.services.release_track import ReleaseTrackService

router = APIRouter(prefix="/admin", tags=["admin"])


class FlagUpdate(BaseModel):
    enabled: bool


class SettingUpdate(BaseModel):
    value: dict[str, Any]
    description: str | None = None


class ReportCreate(BaseModel):
    target_type: str = Field(pattern="^(track|artist|user|release)$")
    target_id: UUID
    report_type: str
    description: str | None = None


class ReportResolve(BaseModel):
    status: str = Field(pattern="^(resolved|rejected|reviewing)$")
    notes: str | None = None
    takedown_track: bool = False


class SuspendRequest(BaseModel):
    reason: str | None = None


# --- Feature flags ---


@router.get("/feature-flags")
async def list_flags(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("feature_flags.read"))],
) -> list[dict[str, Any]]:
    svc = AdminService(session)
    await svc.ensure_default_flags()
    flags = await svc.list_flags()
    return [{"key": f.key, "enabled": f.enabled, "description": f.description} for f in flags]


@router.put("/feature-flags/{key}")
async def set_flag(
    key: str,
    body: FlagUpdate,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("feature_flags.write"))],
) -> dict[str, Any]:
    flag = await AdminService(session).set_flag(key, body.enabled, user.id)
    return {"key": flag.key, "enabled": flag.enabled}


# --- Settings ---


@router.put("/settings/{key}")
async def set_setting(
    key: str,
    body: SettingUpdate,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("settings.write"))],
) -> dict[str, Any]:
    s = await AdminService(session).set_setting(
        key, body.value, user.id, description=body.description
    )
    return {"key": s.key, "value": s.value}


@router.get("/settings/{key}")
async def get_setting(
    key: str,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("settings.read"))],
) -> dict[str, Any]:
    s = await AdminService(session).get_setting(key)
    if s is None:
        return {"key": key, "value": None}
    return {"key": s.key, "value": s.value}


# --- Moderation ---


@router.post("/moderation/reports", status_code=201)
async def create_report(
    body: ReportCreate,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.read", "tracks.write", "artists.write", "tracks.publish", "tracks.takedown"))],
) -> dict[str, Any]:
    # Authenticated users can report; permission is light. Public report can use separate endpoint.
    report = await AdminService(session).create_report(
        reporter_user_id=user.id,
        target_type=body.target_type,
        target_id=body.target_id,
        report_type=ModerationReportType(body.report_type),
        description=body.description,
    )
    return {"id": report.id, "status": report.status.value}


@router.get("/moderation/reports")
async def list_reports(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.takedown"))],
    status: str | None = None,
) -> list[dict[str, Any]]:
    st = ModerationStatus(status) if status else None
    reports = await AdminService(session).list_reports(status=st)
    return [
        {
            "id": r.id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "report_type": r.report_type.value,
            "status": r.status.value,
            "description": r.description,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.post("/moderation/reports/{report_id}/resolve")
async def resolve_report(
    report_id: UUID,
    body: ReportResolve,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.takedown"))],
) -> dict[str, Any]:
    report = await AdminService(session).resolve_report(
        report_id,
        user.id,
        status=ModerationStatus(body.status),
        notes=body.notes,
        takedown_track=body.takedown_track,
    )
    return {"id": report.id, "status": report.status.value}


# --- Users ---


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: UUID,
    body: SuspendRequest,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("users.suspend"))],
) -> dict[str, str]:
    u = await AdminService(session).suspend_user(user_id, user.id, reason=body.reason)
    return {"id": str(u.id), "status": u.status.value}


@router.post("/users/{user_id}/unsuspend")
async def unsuspend_user(
    user_id: UUID,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("users.suspend"))],
) -> dict[str, str]:
    u = await AdminService(session).unsuspend_user(user_id, user.id)
    return {"id": str(u.id), "status": u.status.value}


# --- Audit ---


@router.get("/audit-logs")
async def audit_logs(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("audit_logs.read"))],
    limit: int = 50,
) -> list[dict[str, Any]]:
    logs = await AdminService(session).list_audit_logs(limit=min(limit, 200))
    return [
        {
            "id": log.id,
            "actor_id": log.actor_id,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "result": log.result,
            "reason": log.reason,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


# --- RBAC bootstrap ---


@router.post("/rbac/ensure-defaults")
async def ensure_rbac(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("settings.write"))],
) -> dict[str, str]:
    await RbacService(session).ensure_default_rbac()
    await AdminService(session).ensure_default_flags()
    return {"status": "ok"}


# --- First-party music catalog (admin) ---


class CatalogArtistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country: str = Field(default="CU", min_length=2, max_length=2)
    bio: str | None = Field(default=None, max_length=5000)


class CatalogTrackStatus(BaseModel):
    status: str = Field(pattern="^(draft|hidden|takedown|deleted)$")


def _catalog_slug(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-")[:200] or "artist"


async def _ensure_admin_artist_membership(session: DbSession, user_id: UUID, artist_id: UUID) -> None:
    """Grant the already-authorized catalog administrator the artist-scoped role required by services."""
    artist = await session.get(Artist, artist_id)
    if artist is None or artist.status != "active":
        raise NotFoundError("Artist not found")
    member = await session.scalar(
        select(ArtistMember).where(
            ArtistMember.artist_id == artist_id,
            ArtistMember.user_id == user_id,
        )
    )
    if member is None:
        session.add(ArtistMember(
            artist_id=artist_id,
            user_id=user_id,
            role=ArtistMemberRole.MANAGER,
        ))
    elif member.role not in (ArtistMemberRole.OWNER, ArtistMemberRole.MANAGER, ArtistMemberRole.EDITOR):
        member.role = ArtistMemberRole.MANAGER
    await session.flush()


@router.get("/catalog")
async def get_catalog(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.read"))],
) -> dict[str, Any]:
    artists = list((await session.scalars(select(Artist).order_by(Artist.name))).all())
    rows = (
        await session.execute(
            select(Track, Artist)
            .join(TrackArtist, TrackArtist.track_id == Track.id)
            .join(Artist, Artist.id == TrackArtist.artist_id)
            .order_by(Track.created_at.desc(), TrackArtist.display_order.asc())
            .limit(500)
        )
    ).all()
    assets = (
        await session.execute(
            select(AudioAsset.track_id, AudioAsset.quality, AudioAsset.source_type, AudioAsset.quality_confidence)
            .where(AudioAsset.is_active.is_(True))
        )
    ).all()
    asset_map: dict[UUID, list[dict[str, str]]] = {}
    for track_id, quality, source_type, confidence in assets:
        asset_map.setdefault(track_id, []).append({
            "quality": quality.value,
            "source_type": source_type.value,
            "quality_confidence": confidence.value,
        })
    tracks_by_id: dict[UUID, dict[str, Any]] = {}
    for track, artist in rows:
        item = tracks_by_id.setdefault(track.id, {
            "id": str(track.id),
            "title": track.title,
            "status": track.status.value,
            "duration": track.duration,
            "isrc": track.isrc,
            "explicit": track.explicit,
            "language": track.language,
            "release_date": track.release_date.isoformat() if track.release_date else None,
            "artwork_url": track.artwork_url,
            "release_id": str(track.release_id) if track.release_id else None,
            "created_at": track.created_at.isoformat() if track.created_at else None,
            "artists": [],
            "artist_ids": [],
            "assets": asset_map.get(track.id, []),
        })
        if artist.name not in item["artists"]:
            item["artists"].append(artist.name)
            item["artist_ids"].append(str(artist.id))
    return {
        "artists": [{
            "id": str(a.id), "name": a.name, "country": a.country,
            "status": a.status, "verified": a.verified,
        } for a in artists],
        "tracks": list(tracks_by_id.values()),
    }


@router.post("/catalog/artists", status_code=201)
async def create_catalog_artist(
    body: CatalogArtistCreate,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("artists.write"))],
) -> dict[str, Any]:
    name = body.name.strip()
    if not name:
        raise ValidationError("Artist name cannot be blank")
    slug = _catalog_slug(name)
    if await session.scalar(select(Artist.id).where(Artist.slug == slug)):
        raise ConflictError("Artist slug already exists")
    artist = Artist(
        name=name,
        slug=slug,
        country=body.country.upper(),
        bio=body.bio,
        status="active",
    )
    session.add(artist)
    await session.flush()
    session.add(ArtistMember(
        artist_id=artist.id,
        user_id=user.id,
        role=ArtistMemberRole.OWNER,
    ))
    await AdminService(session).audit(
        actor_id=user.id,
        action="catalog.artist_created",
        target_type="artist",
        target_id=str(artist.id),
        after={"name": artist.name, "slug": artist.slug},
    )
    await session.flush()
    return {"id": str(artist.id), "name": artist.name, "slug": artist.slug, "country": artist.country}


@router.post("/catalog/artists/{artist_id}/tracks", status_code=201)
async def upload_catalog_track(
    artist_id: UUID,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.write"))],
    title: str = Form(..., min_length=1, max_length=255),
    accept_license: bool = Form(...),
    explicit: bool = Form(False),
    language: str = Form("es"),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if not file.filename:
        raise ValidationError("Filename required")
    await _ensure_admin_artist_membership(session, user.id, artist_id)
    result = await ArtistUploadService(session).upload_track(
        user_id=user.id,
        artist_id=artist_id,
        title=title,
        file=file.file,
        filename=file.filename,
        accept_license=accept_license,
        explicit=explicit,
        language=language,
    )
    await AdminService(session).audit(
        actor_id=user.id,
        action="catalog.track_uploaded",
        target_type="track",
        target_id=str(result.track_id),
        after={"artist_id": str(artist_id), "status": result.status},
    )
    return {
        "track_id": str(result.track_id),
        "status": result.status,
        "duration": result.duration,
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.patch("/catalog/tracks/{track_id}")
async def update_catalog_track(
    track_id: UUID,
    body: TrackUpdateRequest,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.write"))],
) -> dict[str, Any]:
    track_artist = await session.scalar(
        select(TrackArtist).where(TrackArtist.track_id == track_id).order_by(TrackArtist.display_order)
    )
    if track_artist is None:
        raise NotFoundError("Track not found")
    await _ensure_admin_artist_membership(session, user.id, track_artist.artist_id)
    track = await ReleaseTrackService(session).update_track(
        user_id=user.id,
        artist_id=track_artist.artist_id,
        track_id=track_id,
        title=body.title,
        isrc=body.isrc,
        explicit=body.explicit,
        language=body.language,
        release_date=body.release_date,
        artwork_url=body.artwork_url,
        release_id=body.release_id,
    )
    return {"track_id": str(track.id), "title": track.title, "status": track.status.value}


@router.post("/catalog/artists/{artist_id}/tracks/{track_id}/publish")
async def publish_catalog_track(
    artist_id: UUID,
    track_id: UUID,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.publish"))],
) -> dict[str, str]:
    await _ensure_admin_artist_membership(session, user.id, artist_id)
    track = await ArtistUploadService(session).publish_track(
        user_id=user.id, artist_id=artist_id, track_id=track_id
    )
    await AdminService(session).audit(
        actor_id=user.id,
        action="catalog.track_published",
        target_type="track",
        target_id=str(track.id),
        after={"status": track.status.value},
    )
    return {"track_id": str(track.id), "status": track.status.value}


@router.post("/catalog/artists/{artist_id}/tracks/{track_id}/status")
async def set_catalog_track_status(
    artist_id: UUID,
    track_id: UUID,
    body: CatalogTrackStatus,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.takedown"))],
) -> dict[str, str]:
    await _ensure_admin_artist_membership(session, user.id, artist_id)
    target = TrackStatus(body.status)
    track = await ReleaseTrackService(session).set_track_status(
        user_id=user.id,
        artist_id=artist_id,
        track_id=track_id,
        status=target,
    )
    await AdminService(session).audit(
        actor_id=user.id,
        action="catalog.track_status_changed",
        target_type="track",
        target_id=str(track.id),
        after={"status": track.status.value},
    )
    return {"track_id": str(track.id), "status": track.status.value}
