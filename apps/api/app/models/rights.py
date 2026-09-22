"""License / rights records for artist-published content."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LicenseStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class LicenseRecord(Base):
    """Rights accepted for artist-uploaded content."""

    __tablename__ = "license_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    track_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("releases.id", ondelete="CASCADE"), nullable=True, index=True
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    storage_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    processing_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    transcoding_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    streaming_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    artwork_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    territory: Mapped[str] = mapped_column(String(16), nullable=False, default="WW")
    duration_note: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rights_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="full")
    license_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus, name="license_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=LicenseStatus.ACTIVE,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
