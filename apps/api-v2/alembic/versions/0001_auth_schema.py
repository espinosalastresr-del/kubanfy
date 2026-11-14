"""Create isolated auth_v2 schema and authentication tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_auth_schema"
down_revision = None
branch_labels = None
depends_on = None
SCHEMA = "auth_v2"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("age", sa.SmallInteger(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("country_of_origin", sa.String(2), nullable=False),
        sa.Column("preferred_content_country", sa.String(2), nullable=True),
        sa.Column("content_country_mode", sa.String(10), nullable=False, server_default="auto"),
        sa.Column("accepted_terms_version", sa.String(80), nullable=False),
        sa.Column("accepted_terms_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_auth_v2_users_email"),
        schema=SCHEMA,
    )
    op.create_index("ix_auth_v2_users_created_at", "users", ["created_at"], schema=SCHEMA)
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_ip", sa.String(64), nullable=True),
        sa.Column("last_country", sa.String(2), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_auth_v2_sessions_token_hash"),
        schema=SCHEMA,
    )
    op.create_index("ix_auth_v2_sessions_user_id", "user_sessions", ["user_id"], schema=SCHEMA)
    op.create_index("ix_auth_v2_sessions_expires_at", "user_sessions", ["expires_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("user_sessions", schema=SCHEMA)
    op.drop_index("ix_auth_v2_users_created_at", table_name="users", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)
    op.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA}"))
