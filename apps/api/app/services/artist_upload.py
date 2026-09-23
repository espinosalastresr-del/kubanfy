"""Artist content upload pipeline.

upload → validate → metadata → audio validation → rights →
transcode → store master → derivatives → publish (optional admin approval)
"""

from __future__ import annotations

import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, NotFoundError, RightsError, ValidationError
from app.core.logging import get_logger
from app.models.artist_member import ArtistMember, ArtistMemberRole
from app.models.music import (
    Artist,
    AudioAsset,
    AudioQuality,
    Release,
    ReleaseType,
    QualityConfidence,
    SourceType,
    Track,
    TrackArtist,
    TrackStatus,
)
from app.models.rights import LicenseRecord, LicenseStatus
from app.services.audio_validation import AudioValidationService
from app.services.job import JobService
from app.services.transcoding import TranscodingService
from app.models.job import JobType
from app.storage import StorageBucket, get_storage
from app.storage.base import StorageProvider

logger = get_logger(__name__)

EDIT_ROLES = {
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


@dataclass
class UploadResult:
    track_id: UUID
    status: str
    master_storage_key: str
    content_hash: str
    duration: float | None
    job_id: UUID | None = None


class ArtistUploadService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: StorageProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.storage = storage or get_storage()
        self.settings = settings or get_settings()
        self.validator = AudioValidationService(self.settings)
        self.transcoder = TranscodingService(self.settings)
        self.jobs = JobService(session)

    async def assert_can_edit(self, user_id: UUID, artist_id: UUID) -> ArtistMember:
        member = await self.session.scalar(
            select(ArtistMember).where(
                ArtistMember.artist_id == artist_id,
                ArtistMember.user_id == user_id,
            )
        )
        if member is None or member.role not in EDIT_ROLES:
            raise ForbiddenError("Not authorized to upload for this artist")
        return member

    async def upload_track(
        self,
        *,
        user_id: UUID,
        artist_id: UUID,
        title: str,
        file_bytes: bytes,
        filename: str,
        accept_license: bool,
        license_version: str = "1.0",
        explicit: bool = False,
        language: str | None = "es",
        enqueue_derivatives: bool = True,
    ) -> UploadResult:
        if not self.settings.feature_artist_publishing:
            raise ForbiddenError("Artist publishing is disabled")

        await self.assert_can_edit(user_id, artist_id)

        artist = await self.session.get(Artist, artist_id)
        if artist is None:
            raise NotFoundError("Artist not found")

        if not accept_license:
            raise RightsError("License must be accepted before upload")

        # Extension check
        ext = Path(filename).suffix.lstrip(".").lower()
        if ext not in self.settings.allowed_audio_ext_list:
            raise ValidationError(
                f"File extension '.{ext}' not allowed",
                details={"allowed": self.settings.allowed_audio_ext_list},
            )

        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ValidationError(f"File exceeds max size of {self.settings.max_upload_size_mb} MB")

        # Write temp and validate
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)

        try:
            probe = await self.validator.validate_for_storage(tmp_path)

            # Every first-party upload starts inside an explicit release.
            # This establishes Artist -> Release -> Track before publication.
            release = Release(
                artist_id=artist_id,
                title=title.strip(),
                type=ReleaseType.SINGLE,
                status=TrackStatus.DRAFT,
            )
            self.session.add(release)
            await self.session.flush()

            track = Track(
                title=title.strip(),
                slug=_slugify(f"{title}-{artist.slug}"),
                duration=probe.duration,
                release_id=release.id,
                album_id=release.id,
                status=TrackStatus.PROCESSING,
                explicit=explicit,
                language=language,
            )
            self.session.add(track)
            await self.session.flush()

            self.session.add(
                TrackArtist(
                    track_id=track.id,
                    artist_id=artist_id,
                    role="main",
                    display_order=0,
                )
            )

            # Rights record
            license_rec = LicenseRecord(
                track_id=track.id,
                release_id=release.id,
                artist_id=artist_id,
                accepted_by_user_id=user_id,
                storage_allowed=True,
                processing_allowed=True,
                transcoding_allowed=True,
                streaming_allowed=True,
                artwork_allowed=True,
                metadata_allowed=True,
                license_version=license_version,
                status=LicenseStatus.ACTIVE,
            )
            self.session.add(license_rec)

            # Store master in permanent bucket
            master_key = (
                f"artists/{artist_id}/tracks/{track.id}/master/"
                f"{probe.content_hash[:16]}.{ext or 'bin'}"
            )
            await self.storage.put(
                master_key,
                file_bytes,
                bucket=StorageBucket.PERMANENT,
                content_type=f"audio/{probe.codec or ext or 'mpeg'}",
            )

            master_asset = AudioAsset(
                track_id=track.id,
                storage_key=master_key,
                codec=probe.codec,
                bitrate=(probe.bitrate // 1000) if probe.bitrate else None,
                bit_depth=probe.bit_depth,
                sample_rate=probe.sample_rate,
                channels=probe.channels,
                duration=probe.duration,
                size=probe.size,
                quality=AudioQuality.LOSSLESS
                if (probe.codec or "").lower() in ("flac", "alac", "pcm_s16le", "pcm_s24le")
                else AudioQuality.MEDIUM,
                quality_confidence=QualityConfidence.VERIFIED,
                source_type=SourceType.ARTIST_UPLOAD,
                content_hash=probe.content_hash,
            )
            self.session.add(master_asset)
            await self.session.flush()

            job_id = None
            if enqueue_derivatives:
                job = await self.jobs.enqueue(
                    JobType.TRANSCODE,
                    payload={
                        "track_id": str(track.id),
                        "master_key": master_key,
                        "artist_id": str(artist_id),
                        "qualities": ["low", "medium"],
                    },
                    correlation_id=str(track.id),
                    idempotency_key=f"transcode:{track.id}",
                )
                job_id = job.id

            logger.info(
                "artist_upload_accepted",
                track_id=str(track.id),
                artist_id=str(artist_id),
                user_id=str(user_id),
                hash=probe.content_hash[:16],
            )
            return UploadResult(
                track_id=track.id,
                status=track.status.value,
                master_storage_key=master_key,
                content_hash=probe.content_hash,
                duration=probe.duration,
                job_id=job_id,
            )
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    async def publish_track(self, *, user_id: UUID, track_id: UUID, artist_id: UUID) -> Track:
        await self.assert_can_edit(user_id, artist_id)
        track = await self.session.get(Track, track_id)
        if track is None:
            raise NotFoundError("Track not found")
        if track.status not in (TrackStatus.PROCESSING, TrackStatus.HIDDEN, TrackStatus.DRAFT):
            if track.status == TrackStatus.PUBLISHED:
                return track
            raise ValidationError(f"Cannot publish track in status {track.status.value}")

        # Validate the complete first-party ownership chain:
        # Artist -> Release -> Track -> AudioAsset -> LicenseRecord.
        release = await self.session.get(Release, track.release_id) if track.release_id else None
        if release is None or release.artist_id != artist_id:
            raise RightsError("Track must belong to a release owned by the publishing artist")

        artist_link = await self.session.scalar(
            select(TrackArtist).where(
                TrackArtist.track_id == track_id,
                TrackArtist.artist_id == artist_id,
            )
        )
        if artist_link is None:
            raise RightsError("Track artist ownership record is required to publish")

        asset = await self.session.scalar(
            select(AudioAsset).where(AudioAsset.track_id == track_id).limit(1)
        )
        if asset is None or not asset.storage_key or not asset.content_hash:
            raise ValidationError(
                "A validated audio asset with storage key and content hash is required to publish"
            )
        if asset.source_type != SourceType.ARTIST_UPLOAD:
            raise RightsError(
                "Published artist catalog tracks require an artist-uploaded audio asset"
            )

        # Publication is allowed only after the offline-friendly playback
        # derivatives are actually present and verified.
        derivative_qualities = await self.session.scalars(
            select(AudioAsset.quality).where(
                AudioAsset.track_id == track_id,
                AudioAsset.source_type == SourceType.DERIVATIVE,
                AudioAsset.quality.in_([AudioQuality.LOW, AudioQuality.MEDIUM]),
                AudioAsset.content_hash.is_not(None),
                AudioAsset.storage_key != "",
            )
        )
        if set(derivative_qualities.all()) != {AudioQuality.LOW, AudioQuality.MEDIUM}:
            raise ValidationError(
                "LOW and MEDIUM verified derivatives are required before publication"
            )

        license_rec = await self.session.scalar(
            select(LicenseRecord).where(
                LicenseRecord.track_id == track_id,
                LicenseRecord.release_id == release.id,
                LicenseRecord.artist_id == artist_id,
                LicenseRecord.status == LicenseStatus.ACTIVE,
            )
        )
        if license_rec is None or not license_rec.streaming_allowed:
            raise RightsError("Active streaming license required to publish")

        track.status = TrackStatus.PUBLISHED
        release.status = TrackStatus.PUBLISHED
        await self.session.flush()
        logger.info("track_published", track_id=str(track_id), user_id=str(user_id))
        return track
