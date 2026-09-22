"""Artist membership and portal roles."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ArtistMemberRole(str, enum.Enum):
    OWNER = "owner"
    MANAGER = "manager"
    EDITOR = "editor"
    ANALYST = "analyst"


class ArtistMember(Base):
    __tablename__ = "artist_members"
    __table_args__ = (
        UniqueConstraint("artist_id", "user_id", name="uq_artist_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[ArtistMemberRole] = mapped_column(
        Enum(
            ArtistMemberRole,
            name="artist_member_role",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ArtistMemberRole.EDITOR,
    )
    permissions: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="Optional extra permission codes, comma-separated"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
