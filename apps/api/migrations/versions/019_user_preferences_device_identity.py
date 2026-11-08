"""Add user preferences and cryptographic device identity.

Revision ID: 019
Revises: 018
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL enum changes are additive and preserve all existing device states.
    op.execute("ALTER TYPE device_status ADD VALUE IF NOT EXISTS 'blocked'")

    op.add_column("devices", sa.Column("public_key", sa.String(length=44), nullable=True))

    op.create_table(
        "user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audio_quality", sa.String(length=16), server_default="auto", nullable=False),
        sa.Column("data_saver", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("wifi_only_downloads", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("theme", sa.String(length=16), server_default="system", nullable=False),
        sa.Column("local_content_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_preferences_user_id", "user_preferences", ["user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
    op.drop_column("devices", "public_key")
    # Preserve old-client compatibility by converting blocked rows and rebuilding
    # the enum without the new value. PostgreSQL cannot directly drop enum values.
    op.execute("UPDATE devices SET status = 'revoked' WHERE status = 'blocked'")
    op.execute("ALTER TYPE device_status RENAME TO device_status_old")
    op.execute("CREATE TYPE device_status AS ENUM ('active', 'revoked', 'suspicious')")
    op.execute(
        "ALTER TABLE devices ALTER COLUMN status TYPE device_status "
        "USING status::text::device_status"
    )
    op.execute("DROP TYPE device_status_old")
