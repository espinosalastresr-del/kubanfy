"""First-party release and track catalog management."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, RightsError, ValidationError
from app.models.artist_member import ArtistMember, ArtistMemberRole
from app.models.job import JobType
from app.models.music import (
    Artist,
    AudioAsset,
    AudioQuality,
    QualityConfidence,
    Release,
    SourceType,
    Track,
    TrackArtist,
    TrackStatus,
)
from app.models.rights import LicenseRecord, LicenseStatus
from app.services.job import JobService

EDIT_ROLES = {
    ArtistMemberRole.OWNER,
    ArtistMemberRole.MANAGER,
    ArtistMemberRole.EDITOR,
}

PUBLISH_ROLES = {
    ArtistMemberRole.OWNER,
    ArtistMemberRole.MANAGER,
    ArtistMemberRole.EDITOR,
}


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:200] or "track"


class ReleaseTrackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _member(
        self, user_id: UUID, artist_id: UUID, roles: set[ArtistMemberRole]
    ) -> ArtistMember:
        member = await self.session.scalar(
            select(ArtistMember).where(
                ArtistMember.artist_id == artist_id,
                ArtistMember.user_id == user_id,
            )
        )
        if member is None or member.role not in roles:
            raise NotFoundError("Artist not found")
        return member

    async def _artist(self, artist_id: UUID) -> Artist:
        artist = await self.session.get(Artist, artist_id)
        if artist is None or artist.status != "active":
            raise NotFoundError("Artist not found")
        return artist

    async def create_release(
        self,
        *,
        user_id: UUID,
        artist_id: UUID,
        title: str,
        type,
        description,
        artwork_asset,
        release_date,
    ) -> Release:
        await self._artist(artist_id)
        await self._member(user_id, artist_id, EDIT_ROLES)
        release = Release(
            artist_id=artist_id,
            title=title.strip(),
            type=type,
            description=description,
            artwork_asset=artwork_asset,
            release_date=release_date,
            status=TrackStatus.DRAFT,
        )
        self.session.add(release)
        await self.session.flush()
        return release

    async def update_release(
        self,
        *,
        user_id: UUID,
        artist_id: UUID,
        release_id: UUID,
        title: str,
        type,
        description,
        artwork_asset,
        release_date,
    ) -> Release:
        await self._member(user_id, artist_id, EDIT_ROLES)
        release = await self.session.get(Release, release_id)
        if release is None or release.artist_id != artist_id:
            raise NotFoundError("Release not found")
        if release.status == TrackStatus.DELETED:
            raise ValidationError("Deleted release cannot be edited")
        if release.status == TrackStatus.PUBLISHED:
            # Metadata can be corrected while published, but publication state is unchanged.
            pass
        release.title = title.strip()
        release.type = type
        release.description = description
        release.artwork_asset = artwork_asset
        release.release_date = release_date
        await self.session.flush()
        return release

    async def set_release_status(
        self, *, user_id: UUID, artist_id: UUID, release_id: UUID, status: TrackStatus
    ) -> Release:
        await self._member(user_id, artist_id, PUBLISH_ROLES)
        release = await self.session.get(Release, release_id)
        if release is None or release.artist_id != artist_id:
            raise NotFoundError("Release not found")
        if release.status == TrackStatus.DELETED:
            raise ValidationError("Deleted release cannot change status")

        if status == TrackStatus.PUBLISHED:
            tracks = list(
                (
                    await self.session.scalars(select(Track).where(Track.release_id == release_id))
                ).all()
            )
            if not tracks:
                raise ValidationError("Release must contain at least one track")
            if any(t.status != TrackStatus.PUBLISHED for t in tracks):
                raise ValidationError(
                    "All release tracks must be published before publishing the release"
                )
            release.status = TrackStatus.PUBLISHED
        elif status in (TrackStatus.HIDDEN, TrackStatus.TAKEDOWN):
            release.status = status
            if status in (TrackStatus.HIDDEN, TrackStatus.TAKEDOWN):
                await self.session.execute(
                    Track.__table__.update()
                    .where(Track.release_id == release_id, Track.status == TrackStatus.PUBLISHED)
                    .values(status=status)
                )
        elif status == TrackStatus.DRAFT:
            if release.status == TrackStatus.DELETED:
                raise ValidationError("Deleted release cannot return to draft")
            release.status = status
        elif status == TrackStatus.DELETED:
            release.status = status
            await self.session.execute(
                Track.__table__.update()
                .where(Track.release_id == release_id, Track.status != TrackStatus.DELETED)
                .values(status=TrackStatus.DELETED)
            )
        else:
            raise ValidationError(f"Unsupported release status: {status.value}")

        await self.session.flush()
        return release

    async def schedule_release(
        self,
        *,
        user_id: UUID,
        artist_id: UUID,
        release_id: UUID,
        publish_at: datetime | None,
        unpublish_at: datetime | None,
    ) -> Release:
        await self._member(user_id, artist_id, PUBLISH_ROLES)
        release = await self.session.get(Release, release_id)
        if release is None or release.artist_id != artist_id:
            raise NotFoundError("Release not found")
        if release.status == TrackStatus.DELETED:
            raise ValidationError("Deleted release cannot be scheduled")

        now = datetime.now(UTC)
        if publish_at is not None:
            if publish_at.tzinfo is None:
                publish_at = publish_at.replace(tzinfo=UTC)
            if publish_at <= now:
                raise ValidationError("publish_at must be in the future")
        if unpublish_at is not None:
            if unpublish_at.tzinfo is None:
                unpublish_at = unpublish_at.replace(tzinfo=UTC)
            if unpublish_at <= now:
                raise ValidationError("unpublish_at must be in the future")
        if publish_at and unpublish_at and unpublish_at <= publish_at:
            raise ValidationError("unpublish_at must be after publish_at")
        if publish_at is not None:
            track_count = await self.session.scalar(
                select(Track.id).where(Track.release_id == release_id).limit(1)
            )
            if track_count is None:
                raise ValidationError("Release must contain at least one track before scheduling")

        release.scheduled_publish_at = publish_at
        release.scheduled_unpublish_at = unpublish_at
        scheduler = JobService(self.session)
        if publish_at:
            await scheduler.enqueue(
                JobType.PUBLICATION_SCHEDULE,
                {
                    "release_id": str(release.id),
                    "action": "publish",
                    "scheduled_at": publish_at.isoformat(),
                },
                run_at=publish_at,
                idempotency_key=f"release:{release.id}:publish:{publish_at.isoformat()}",
            )
        if unpublish_at:
            await scheduler.enqueue(
                JobType.PUBLICATION_SCHEDULE,
                {
                    "release_id": str(release.id),
                    "action": "unpublish",
                    "scheduled_at": unpublish_at.isoformat(),
                },
                run_at=unpublish_at,
                idempotency_key=f"release:{release.id}:unpublish:{unpublish_at.isoformat()}",
            )
        await self.session.flush()
        return release

    async def update_track(
        self,
        *,
        user_id: UUID,
        artist_id: UUID,
        track_id: UUID,
        title: str,
        isrc: str | None,
        explicit: bool,
        language: str | None,
        release_date,
        artwork_url: str | None,
        release_id: UUID | None,
    ) -> Track:
        await self._member(user_id, artist_id, EDIT_ROLES)
        track = await self.session.get(Track, track_id)
        if track is None:
            raise NotFoundError("Track not found")
        ownership = await self.session.scalar(
            select(TrackArtist).where(
                TrackArtist.track_id == track_id, TrackArtist.artist_id == artist_id
            )
        )
        if ownership is None:
            raise NotFoundError("Track not found")
        if track.status == TrackStatus.DELETED:
            raise ValidationError("Deleted track cannot be edited")

        if release_id is not None:
            release = await self.session.get(Release, release_id)
            if (
                release is None
                or release.artist_id != artist_id
                or release.status == TrackStatus.DELETED
            ):
                raise ValidationError("Target release is invalid")
            track.release_id = release_id
            track.album_id = release_id
        elif track.release_id is not None:
            release = await self.session.get(Release, track.release_id)
            if release is not None and release.status == TrackStatus.DELETED:
                raise ValidationError("Track cannot remain attached to a deleted release")

        track.title = title.strip()
        track.slug = _slugify(f"{title}-{artist_id}")
        track.isrc = isrc
        track.explicit = explicit
        track.language = language
        track.release_date = release_date
        track.artwork_url = artwork_url
        await self.session.flush()
        return track

    async def set_track_status(
        self, *, user_id: UUID, artist_id: UUID, track_id: UUID, status: TrackStatus
    ) -> Track:
        await self._member(user_id, artist_id, PUBLISH_ROLES)
        track = await self.session.get(Track, track_id)
        if track is None:
            raise NotFoundError("Track not found")
        ownership = await self.session.scalar(
            select(TrackArtist).where(
                TrackArtist.track_id == track_id, TrackArtist.artist_id == artist_id
            )
        )
        if ownership is None:
            raise NotFoundError("Track not found")
        if track.status == TrackStatus.DELETED:
            raise ValidationError("Deleted track cannot change status")

        if status == TrackStatus.PUBLISHED:
            release = (
                await self.session.get(Release, track.release_id) if track.release_id else None
            )
            if release is None or release.artist_id != artist_id:
                raise RightsError("Track must belong to the publishing artist's release")
            asset = await self.session.scalar(
                select(AudioAsset)
                .where(
                    AudioAsset.track_id == track_id,
                    AudioAsset.is_active.is_(True),
                    AudioAsset.storage_key != "",
                    AudioAsset.content_hash.is_not(None),
                    AudioAsset.source_type == SourceType.ARTIST_UPLOAD,
                )
                .order_by(AudioAsset.version.desc())
                .limit(1)
            )
            if asset is None:
                raise ValidationError("Validated active artist audio asset required")
            derivative_qualities = await self.session.scalars(
                select(AudioAsset.quality).where(
                    AudioAsset.track_id == track_id,
                    AudioAsset.is_active.is_(True),
                    AudioAsset.source_type == SourceType.DERIVATIVE,
                    AudioAsset.version == asset.version,
                    AudioAsset.quality.in_([AudioQuality.LOW, AudioQuality.MEDIUM]),
                    AudioAsset.storage_key != "",
                    AudioAsset.content_hash.is_not(None),
                    AudioAsset.quality_confidence == QualityConfidence.VERIFIED,
                )
            )
            if set(derivative_qualities.all()) != {AudioQuality.LOW, AudioQuality.MEDIUM}:
                raise ValidationError("LOW and MEDIUM verified derivatives are required")
            license_rec = await self.session.scalar(
                select(LicenseRecord).where(
                    LicenseRecord.track_id == track_id,
                    LicenseRecord.artist_id == artist_id,
                    LicenseRecord.status == LicenseStatus.ACTIVE,
                    LicenseRecord.streaming_allowed.is_(True),
                )
            )
            if license_rec is None:
                raise RightsError("Active streaming license required")
        elif status == TrackStatus.DELETED:
            pass
        elif status not in (TrackStatus.DRAFT, TrackStatus.HIDDEN, TrackStatus.TAKEDOWN):
            raise ValidationError(f"Unsupported track status: {status.value}")

        track.status = status
        await self.session.flush()
        return track
