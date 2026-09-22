"""Payment orders, analytics events, daily aggregates, ranking snapshots

Revision ID: 007
Revises: 006
Create Date: 2026-09-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    payment_method = sa.Enum(
        "bank_transfer", "cash", "google_play", "other", name="payment_method"
    )
    payment_status = sa.Enum(
        "pending",
        "under_review",
        "approved",
        "rejected",
        "refunded",
        "expired",
        name="payment_status",
    )
    payment_method.create(op.get_bind(), checkfirst=True)
    payment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "payment_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="CUP"),
        sa.Column("method", payment_method, nullable=False, server_default="bank_transfer"),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("proof_storage_key", sa.String(length=512), nullable=True),
        sa.Column("status", payment_status, nullable=False, server_default="pending"),
        sa.Column("plan_code", sa.String(length=32), nullable=True),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_payment_orders_user_id", "payment_orders", ["user_id"])
    op.create_index("ix_payment_orders_status", "payment_orders", ["status"])
    op.create_index("ix_payment_orders_reference", "payment_orders", ["reference"])
    op.create_index("ix_payment_orders_idempotency_key", "payment_orders", ["idempotency_key"], unique=True)

    op.create_table(
        "analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("region", sa.String(length=64), nullable=True),
        sa.Column("app_version", sa.String(length=32), nullable=True),
        sa.Column("os", sa.String(length=32), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_analytics_events_event_id", "analytics_events", ["event_id"], unique=True)
    op.create_index("ix_analytics_events_timestamp", "analytics_events", ["timestamp"])
    op.create_index("ix_analytics_events_user_id", "analytics_events", ["user_id"])
    op.create_index("ix_analytics_events_track_id", "analytics_events", ["track_id"])
    op.create_index("ix_analytics_events_artist_id", "analytics_events", ["artist_id"])
    op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"])
    op.create_index("ix_analytics_events_country", "analytics_events", ["country"])
    op.create_index("ix_analytics_events_session_id", "analytics_events", ["session_id"])

    op.create_table(
        "analytics_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.String(length=10), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("plays", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qualified_plays", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_listeners", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downloads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skips", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("favorites", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("playlist_adds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completions", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_daily_date", "analytics_daily", ["date"])
    op.create_index("ix_analytics_daily_country", "analytics_daily", ["country"])
    op.create_index("ix_analytics_daily_track_id", "analytics_daily", ["track_id"])
    op.create_index("ix_analytics_daily_artist_id", "analytics_daily", ["artist_id"])

    op.create_table(
        "ranking_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("scope_value", sa.String(length=64), nullable=True),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("period_key", sa.String(length=32), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ranking_snapshots_scope", "ranking_snapshots", ["scope"])
    op.create_index("ix_ranking_snapshots_scope_value", "ranking_snapshots", ["scope_value"])
    op.create_index("ix_ranking_snapshots_period_key", "ranking_snapshots", ["period_key"])
    op.create_index("ix_ranking_snapshots_track_id", "ranking_snapshots", ["track_id"])


def downgrade() -> None:
    op.drop_table("ranking_snapshots")
    op.drop_table("analytics_daily")
    op.drop_table("analytics_events")
    op.drop_table("payment_orders")
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS payment_method")
