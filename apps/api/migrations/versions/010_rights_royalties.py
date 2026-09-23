"""Collaborator splits and royalty accounting skeleton.

Revision ID: 010
Revises: 009
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table("collaborator_splits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.String(16), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="artist"),
        sa.Column("share_bps", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_type","scope_id","artist_id","generation",name="uq_collaborator_split_generation"))
    op.create_index("ix_collaborator_splits_scope_type","collaborator_splits",["scope_type"])
    op.create_index("ix_collaborator_splits_scope_id","collaborator_splits",["scope_id"])
    op.create_index("ix_collaborator_splits_artist_id","collaborator_splits",["artist_id"])
    op.create_index("ix_collaborator_splits_active","collaborator_splits",["active"])
    op.create_table("royalty_accounts",
        sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("artist_id",postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("currency",sa.String(3),nullable=False,server_default="CUP"),
        sa.Column("status",sa.String(16),nullable=False,server_default="active"),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.ForeignKeyConstraint(["artist_id"],["artists.id"],ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("artist_id"))
    op.create_index("ix_royalty_accounts_artist_id","royalty_accounts",["artist_id"],unique=True)
    op.create_table("royalty_ledger_entries",
        sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("account_id",postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("amount_cents",sa.BigInteger(),nullable=False),
        sa.Column("currency",sa.String(3),nullable=False,server_default="CUP"),
        sa.Column("direction",sa.String(16),nullable=False,server_default="credit"),
        sa.Column("source_type",sa.String(32),nullable=False),
        sa.Column("source_id",postgresql.UUID(as_uuid=True),nullable=True),
        sa.Column("idempotency_key",sa.String(160),nullable=False),
        sa.Column("metadata",postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.ForeignKeyConstraint(["account_id"],["royalty_accounts.id"],ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("idempotency_key",name="uq_royalty_ledger_idempotency"))
    op.create_index("ix_royalty_ledger_entries_account_id","royalty_ledger_entries",["account_id"])
    op.create_table("royalty_settlements",
        sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("account_id",postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("period_start",sa.DateTime(timezone=True),nullable=False),
        sa.Column("period_end",sa.DateTime(timezone=True),nullable=False),
        sa.Column("gross_cents",sa.BigInteger(),nullable=False,server_default="0"),
        sa.Column("net_cents",sa.BigInteger(),nullable=False,server_default="0"),
        sa.Column("currency",sa.String(3),nullable=False,server_default="CUP"),
        sa.Column("status",sa.String(16),nullable=False,server_default="pending"),
        sa.Column("idempotency_key",sa.String(160),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.ForeignKeyConstraint(["account_id"],["royalty_accounts.id"],ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("idempotency_key",name="uq_royalty_settlement_idempotency"))
    op.create_index("ix_royalty_settlements_account_id","royalty_settlements",["account_id"])

def downgrade() -> None:
    op.drop_table("royalty_settlements")
    op.drop_table("royalty_ledger_entries")
    op.drop_table("royalty_accounts")
    op.drop_table("collaborator_splits")
