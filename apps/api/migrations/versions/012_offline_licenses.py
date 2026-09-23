"""Create device-bound offline licenses.

Revision ID: 012_offline_licenses
Revises: 011_entitlement_payment_idempotency
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "offline_licenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("quality", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_offline_license_token_hash"),
    )
    op.create_index("ix_offline_licenses_user_id", "offline_licenses", ["user_id"])
    op.create_index("ix_offline_licenses_device_id", "offline_licenses", ["device_id"])
    op.create_index("ix_offline_licenses_track_id", "offline_licenses", ["track_id"])
    op.create_index("ix_offline_licenses_token_hash", "offline_licenses", ["token_hash"])
    op.create_index("ix_offline_licenses_expires_at", "offline_licenses", ["expires_at"])
    op.create_index("ix_offline_licenses_revoked", "offline_licenses", ["revoked"])


def downgrade() -> None:
    op.drop_index("ix_offline_licenses_revoked", table_name="offline_licenses")
    op.drop_index("ix_offline_licenses_expires_at", table_name="offline_licenses")
    op.drop_index("ix_offline_licenses_token_hash", table_name="offline_licenses")
    op.drop_index("ix_offline_licenses_track_id", table_name="offline_licenses")
    op.drop_index("ix_offline_licenses_device_id", table_name="offline_licenses")
    op.drop_index("ix_offline_licenses_user_id", table_name="offline_licenses")
    op.drop_table("offline_licenses")
