"""Discovery and ranking service.

Signals: unique listeners, plays, qualified plays, completion, growth,
downloads, playlist adds, favorites, skips, geography, recency.
Weights are configurable via settings (defaults below).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.analytics import AnalyticsEvent, RankingSnapshot
from app.models.music import Artist, Track, TrackStatus
from app.models.playlist import Favorite, FavoriteType

logger = get_logger(__name__)

# Configurable weights (can move to system_settings later)
DEFAULT_WEIGHTS = {
    "qualified_play": 3.0,
    "play_start": 1.0,
    "play_100": 2.0,
    "favorite": 2.5,
    "playlist_add": 2.0,
    "download_complete": 1.5,
    "skip": -0.5,
}


class DiscoveryService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def local_artists(self, country: str, *, limit: int = 20) -> list[Artist]:
        result = await self.session.execute(
            select(Artist)
            .where(Artist.country == country.upper(), Artist.status == "active")
            .order_by(Artist.verified.desc(), Artist.name)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def new_releases(self, *, limit: int = 20) -> list[Track]:
        result = await self.session.execute(
            select(Track)
            .where(Track.status == TrackStatus.PUBLISHED)
            .order_by(desc(Track.release_date), desc(Track.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def top_tracks(
        self,
        *,
        country: str | None = None,
        period_hours: int = 24,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Score tracks from recent analytics events. Fallback to newest published."""
        since = datetime.now(UTC) - timedelta(hours=period_hours)
        q = (
            select(
                AnalyticsEvent.track_id,
                AnalyticsEvent.event_type,
                func.count().label("cnt"),
            )
            .where(
                AnalyticsEvent.timestamp >= since,
                AnalyticsEvent.track_id.is_not(None),
            )
            .group_by(AnalyticsEvent.track_id, AnalyticsEvent.event_type)
        )
        if country:
            q = q.where(AnalyticsEvent.country == country.upper())

        rows = (await self.session.execute(q)).all()
        scores: dict[UUID, float] = {}
        metrics: dict[UUID, dict[str, int]] = {}
        for track_id, event_type, cnt in rows:
            if track_id is None:
                continue
            w = DEFAULT_WEIGHTS.get(event_type, 0.1)
            scores[track_id] = scores.get(track_id, 0.0) + w * cnt
            metrics.setdefault(track_id, {})[event_type] = cnt

        if not scores:
            # Fallback: newest published tracks
            tracks = await self.new_releases(limit=limit)
            return [
                {
                    "rank": i + 1,
                    "track_id": t.id,
                    "title": t.title,
                    "score": 0.0,
                    "metrics": {},
                }
                for i, t in enumerate(tracks)
            ]

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        track_ids = [tid for tid, _ in ranked]
        track_map = {
            t.id: t
            for t in (
                await self.session.execute(select(Track).where(Track.id.in_(track_ids)))
            ).scalars().all()
        }

        out: list[dict[str, Any]] = []
        for i, (tid, score) in enumerate(ranked):
            t = track_map.get(tid)
            out.append(
                {
                    "rank": i + 1,
                    "track_id": tid,
                    "title": t.title if t else None,
                    "score": round(score, 3),
                    "metrics": metrics.get(tid, {}),
                }
            )
        return out

    async def home(
        self, *, country: str | None = None
    ) -> dict[str, Any]:
        country = (country or self.settings.default_country).upper()
        local = await self.local_artists(country, limit=10)
        top = await self.top_tracks(country=country, limit=20)
        top_global = await self.top_tracks(country=None, limit=20)
        new = await self.new_releases(limit=15)
        return {
            "country": country,
            "local_artists": [
                {"id": a.id, "name": a.name, "slug": a.slug, "verified": a.verified}
                for a in local
            ],
            "top_50_country": top,
            "top_50_global": top_global,
            "new_releases": [
                {"id": t.id, "title": t.title, "duration": t.duration} for t in new
            ],
            "trending": top[:10],
            "viral_by_country": top[:10],
        }

    async def save_ranking_snapshot(
        self,
        items: list[dict[str, Any]],
        *,
        scope: str,
        scope_value: str | None,
        period: str,
        period_key: str,
    ) -> int:
        count = 0
        for item in items:
            snap = RankingSnapshot(
                scope=scope,
                scope_value=scope_value,
                period=period,
                period_key=period_key,
                track_id=item["track_id"],
                rank=item["rank"],
                score=float(item.get("score") or 0),
                metrics=item.get("metrics") or {},
            )
            self.session.add(snap)
            count += 1
        await self.session.flush()
        return count
