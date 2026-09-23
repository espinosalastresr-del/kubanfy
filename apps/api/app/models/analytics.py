"""Analytics events and ranking snapshots.

Artists only receive aggregated metrics — never raw PII or exact location.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    track_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    artist_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artists.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    os: Mapped[str | None] = mapped_column(String(32), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class AnalyticsDaily(Base):
    """Pre-aggregated daily stats — dashboards should prefer this over raw events."""

    __tablename__ = "analytics_daily"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    country: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    track_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    artist_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    plays: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qualified_plays: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_listeners: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skips: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    favorites: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    playlist_adds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # country|global|region
    scope_value: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False)  # hourly|daily|weekly
    period_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
