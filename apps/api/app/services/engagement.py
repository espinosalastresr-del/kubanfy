"""Server-side qualification of plays, downloads and shares.

Client events are treated as claims, not as authoritative metrics. A metric is
qualified only after the server validates a short-lived, bound workflow.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.analytics import AnalyticsEvent
from app.models.engagement import DownloadReceipt, PlaybackSession, ShareLink, ShareOpen
from app.models.music import AudioAsset, AudioQuality, Track, TrackStatus
from app.services.entitlement import EntitlementService

logger = get_logger(__name__)

PLAY_QUALIFY_MS = 30_000
HEARTBEAT_MAX_GAP_SECONDS = 30
PLAYBACK_CLOCK_SKEW_MS = 3_000
DOWNLOAD_TICKET_TTL = timedelta(hours=24)
SHARE_TTL = timedelta(days=30)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _event_id(prefix: str, value: str) -> str:
    return f"{prefix}:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]}"


class EngagementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _asset(self, track_id: UUID, quality: str) -> AudioAsset:
        asset = await self.session.scalar(
            select(AudioAsset)
            .where(
                AudioAsset.track_id == track_id,
                AudioAsset.quality == quality,
                AudioAsset.is_active.is_(True),
                AudioAsset.content_hash.is_not(None),
                AudioAsset.storage_key.is_not(None),
            )
            .order_by(AudioAsset.version.desc())
        )
        if asset is None:
            raise NotFoundError("Audio asset not available")
        return asset

    async def start_playback(
        self,
        *,
        user_id: UUID | None,
        device_id: str | None,
        session_id: str | None,
        track_id: UUID,
        quality: str,
        country: str | None,
    ) -> tuple[PlaybackSession, str]:
        if quality not in {q.value for q in AudioQuality}:
            raise ValidationError("Unsupported audio quality")
        track = await self.session.scalar(select(Track).where(Track.id == track_id))
        if track is None or track.status != TrackStatus.PUBLISHED:
            raise NotFoundError("Track not available")
        if user_id is not None:
            ent = EntitlementService(self.session)
            await ent.require_track_access(user_id, track_id)
            await ent.require_quality_access(user_id, quality)
        asset = await self._asset(track_id, quality)

        token = secrets.token_urlsafe(32)
        row = PlaybackSession(
            token_hash=_hash_token(token),
            user_id=user_id,
            device_id=device_id,
            session_id=session_id,
            track_id=track_id,
            asset_version=asset.version,
            content_hash=asset.content_hash,
            quality=quality,
            country=(country or "CU").upper()[:2],
        )
        self.session.add(row)
        await self.session.flush()
        return row, token

    async def heartbeat(
        self,
        *,
        token: str,
        position_ms: int,
        paused: bool = False,
        completed: bool = False,
    ) -> PlaybackSession:
        if position_ms < 0:
            raise ValidationError("position_ms must be non-negative")
        row = await self.session.scalar(
            select(PlaybackSession).where(PlaybackSession.token_hash == _hash_token(token)).with_for_update()
        )
        if row is None:
            raise AuthError("Invalid playback session")
        now = datetime.now(UTC)
        if row.qualified_at is not None:
            return row
        if (now - row.started_at).total_seconds() > 6 * 3600:
            raise AuthError("Playback session expired")

        if row.last_heartbeat_at is None:
            wall_ms = min(10_000, max(0, int((now - row.started_at).total_seconds() * 1000)))
        else:
            wall_ms = min(
                HEARTBEAT_MAX_GAP_SECONDS * 1000,
                max(0, int((now - row.last_heartbeat_at).total_seconds() * 1000)),
            )

        position_delta = position_ms - row.last_position_ms
        if position_delta < 0:
            row.suspicious_score += 1
            position_delta = 0
        max_progress = wall_ms + PLAYBACK_CLOCK_SKEW_MS
        if position_delta > max_progress:
            row.suspicious_score += 2
            position_delta = max_progress

        if not paused:
            row.listened_ms += min(position_delta, max_progress)
        row.last_position_ms = max(row.last_position_ms, position_ms)
        row.last_heartbeat_at = now

        if completed:
            row.completed_at = now

        if row.listened_ms >= PLAY_QUALIFY_MS and row.qualified_at is None:
            row.qualified_at = now
            await self._record_qualified_play(row)

        await self.session.flush()
        return row

    async def _record_qualified_play(self, row: PlaybackSession) -> None:
        event_id = _event_id("qualified-play", str(row.id))
        existing = await self.session.scalar(
            select(AnalyticsEvent).where(AnalyticsEvent.event_id == event_id)
        )
        if existing is None:
            self.session.add(
                AnalyticsEvent(
                    event_id=event_id,
                    user_id=row.user_id,
                    session_id=row.session_id,
                    device_id=row.device_id,
                    track_id=row.track_id,
                    event_type="play_qualified",
                    country=row.country,
                    platform="mobile",
                    metadata_json={
                        "qualified_ms": row.listened_ms,
                        "asset_version": row.asset_version,
                        "content_hash": row.content_hash,
                        "quality": row.quality,
                        "suspicious_score": row.suspicious_score,
                    },
                )
            )

    async def issue_download_ticket(
        self,
        *,
        user_id: UUID,
        device_id: str | None,
        track_id: UUID,
        quality: str,
    ) -> tuple[DownloadReceipt, str]:
        ent = EntitlementService(self.session)
        await ent.require_download_access(user_id)
        await ent.require_track_access(user_id, track_id)
        await ent.require_quality_access(user_id, quality)
        track = await self.session.scalar(select(Track).where(Track.id == track_id))
        if track is None or track.status != TrackStatus.PUBLISHED:
            raise NotFoundError("Track not available")
        asset = await self._asset(track_id, quality)

        token = secrets.token_urlsafe(32)
        row = DownloadReceipt(
            ticket_hash=_hash_token(token),
            user_id=user_id,
            device_id=device_id,
            track_id=track_id,
            asset_version=asset.version,
            content_hash=asset.content_hash,
            quality=quality,
        )
        self.session.add(row)
        await self.session.flush()
        return row, token

    async def complete_download(
        self,
        *,
        user_id: UUID,
        token: str,
        size_bytes: int | None,
        device_id: str | None = None,
    ) -> DownloadReceipt:
        row = await self.session.scalar(
            select(DownloadReceipt).where(DownloadReceipt.ticket_hash == _hash_token(token)).with_for_update()
        )
        if row is None or row.user_id != user_id:
            raise AuthError("Invalid download ticket")
        if row.device_id is not None and row.device_id != device_id:
            raise AuthError("Download ticket device mismatch")
        if row.completed_at is not None:
            return row
        if datetime.now(UTC) - row.issued_at > DOWNLOAD_TICKET_TTL:
            raise AuthError("Download ticket expired")

        asset = await self._asset(row.track_id, row.quality)
        if asset.version != row.asset_version or asset.content_hash != row.content_hash:
            raise AuthError("Download asset changed; issue a new ticket")

        if size_bytes is not None and size_bytes < 0:
            raise ValidationError("Invalid download size")
        row.verified_size = size_bytes
        row.completed_at = datetime.now(UTC)
        await self.session.flush()

        event_id = _event_id("qualified-download", str(row.id))
        existing = await self.session.scalar(
            select(AnalyticsEvent).where(AnalyticsEvent.event_id == event_id)
        )
        if existing is None:
            self.session.add(
                AnalyticsEvent(
                    event_id=event_id,
                    user_id=row.user_id,
                    device_id=row.device_id,
                    track_id=row.track_id,
                    event_type="download_complete",
                    metadata_json={
                        "asset_version": row.asset_version,
                        "content_hash": row.content_hash,
                        "quality": row.quality,
                        "verified_size": size_bytes,
                    },
                )
            )
        return row

    async def create_share(
        self, *, user_id: UUID | None, track_id: UUID
    ) -> tuple[ShareLink, str]:
        track = await self.session.scalar(select(Track).where(Track.id == track_id))
        if track is None or track.status != TrackStatus.PUBLISHED:
            raise NotFoundError("Track not available")
        token = secrets.token_urlsafe(32)
        row = ShareLink(
            token_hash=_hash_token(token),
            creator_user_id=user_id,
            track_id=track_id,
            expires_at=datetime.now(UTC) + SHARE_TTL,
        )
        self.session.add(row)
        await self.session.flush()
        return row, token

    async def open_share(
        self,
        *,
        token: str,
        recipient_key: str,
        recipient_user_id: UUID | None = None,
    ) -> ShareLink:
        row = await self.session.scalar(
            select(ShareLink).where(ShareLink.token_hash == _hash_token(token)).with_for_update()
        )
        if row is None or row.expires_at <= datetime.now(UTC):
            raise NotFoundError("Share link expired or invalid")
        if row.creator_user_id and recipient_user_id == row.creator_user_id:
            return row
        if not recipient_key:
            raise ValidationError("recipient_key is required")

        existing = await self.session.scalar(
            select(ShareOpen).where(
                ShareOpen.share_link_id == row.id,
                ShareOpen.recipient_key == recipient_key,
            )
        )
        if existing is None:
            self.session.add(ShareOpen(share_link_id=row.id, recipient_key=recipient_key))
            row.open_count += 1
            row.qualified_share = True
            self.session.add(
                AnalyticsEvent(
                    event_id=_event_id("qualified-share", f"{row.id}:{recipient_key}"),
                    user_id=recipient_user_id,
                    track_id=row.track_id,
                    event_type="share",
                    metadata_json={"qualified": True},
                )
            )
            await self.session.flush()
        return row
