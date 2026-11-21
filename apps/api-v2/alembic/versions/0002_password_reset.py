"""Add hashed, single-use password reset tokens."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_password_reset"
down_revision = "0001_auth_schema"
branch_labels = None
depends_on = None
SCHEMA = "auth_v2"


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_auth_v2_password_reset_token_hash"),
        schema=SCHEMA,
    )
    op.create_index("ix_auth_v2_password_reset_user_id", "password_reset_tokens", ["user_id"], schema=SCHEMA)
    op.create_index("ix_auth_v2_password_reset_expires_at", "password_reset_tokens", ["expires_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_auth_v2_password_reset_expires_at", table_name="password_reset_tokens", schema=SCHEMA)
    op.drop_index("ix_auth_v2_password_reset_user_id", table_name="password_reset_tokens", schema=SCHEMA)
    op.drop_table("password_reset_tokens", schema=SCHEMA)
