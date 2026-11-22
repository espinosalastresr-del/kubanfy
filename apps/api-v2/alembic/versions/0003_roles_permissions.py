"""Add server-side RBAC roles and permissions to auth_v2."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import table, column
from sqlalchemy import String, Text
import uuid

revision = "0003_roles_permissions"
down_revision = "0002_password_reset"
branch_labels = None
depends_on = None
SCHEMA = "auth_v2"

ROLE_DEFS = [
    ("free", "Cuenta gratuita"),
    ("premium", "Cuenta premium"),
    ("artist", "Cuenta de artista"),
    ("admin", "Administrador de la plataforma"),
]
PERMISSION_DEFS = [
    ("account.self.read", "Consultar el propio perfil"),
    ("music.stream", "Reproducir música"),
    ("playlist.manage.self", "Administrar listas propias"),
    ("premium.offline.download", "Descargas offline premium"),
    ("artist.catalog.manage", "Administrar catálogo de artista"),
    ("artist.analytics.read", "Consultar estadísticas de artista"),
    ("admin.dashboard.access", "Acceder al panel administrativo"),
    ("admin.users.manage", "Administrar usuarios"),
    ("admin.roles.manage", "Administrar roles y permisos"),
    ("admin.catalog.manage", "Administrar catálogo global"),
    ("admin.platform.settings", "Administrar configuración de plataforma"),
    ("admin.audit.read", "Consultar auditoría"),
]
ROLE_PERMISSIONS = {
    "free": ["account.self.read", "music.stream", "playlist.manage.self"],
    "premium": ["account.self.read", "music.stream", "playlist.manage.self", "premium.offline.download"],
    "artist": ["account.self.read", "music.stream", "playlist.manage.self", "artist.catalog.manage", "artist.analytics.read"],
    "admin": [code for code, _ in PERMISSION_DEFS],
}

def upgrade():
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("description", sa.Text()),
        sa.UniqueConstraint("name", name="uq_auth_v2_roles_name"),
        schema=SCHEMA,
    )
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.UniqueConstraint("code", name="uq_auth_v2_permissions_code"),
        schema=SCHEMA,
    )
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True)),
        sa.ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], [f"{SCHEMA}.roles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_auth_v2_user_role"),
        schema=SCHEMA,
    )
    op.create_index("ix_auth_v2_user_roles_user_id", "user_roles", ["user_id"], schema=SCHEMA)
    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], [f"{SCHEMA}.roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], [f"{SCHEMA}.permissions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_auth_v2_role_permission"),
        schema=SCHEMA,
    )
    op.create_index("ix_auth_v2_role_permissions_role_id", "role_permissions", ["role_id"], schema=SCHEMA)
    roles = table("roles", column("id", postgresql.UUID(as_uuid=True)), column("name", String), column("description", Text), schema=SCHEMA)
    permissions = table("permissions", column("id", postgresql.UUID(as_uuid=True)), column("code", String), column("description", Text), schema=SCHEMA)
    rp = table("role_permissions", column("id", postgresql.UUID(as_uuid=True)), column("role_id", postgresql.UUID(as_uuid=True)), column("permission_id", postgresql.UUID(as_uuid=True)), schema=SCHEMA)
    role_ids = {}
    permission_ids = {}
    for name, desc in ROLE_DEFS:
        role_ids[name] = uuid.uuid4()
        op.bulk_insert(roles, [{"id": role_ids[name], "name": name, "description": desc}])
    for code, desc in PERMISSION_DEFS:
        permission_ids[code] = uuid.uuid4()
        op.bulk_insert(permissions, [{"id": permission_ids[code], "code": code, "description": desc}])
    for role, codes in ROLE_PERMISSIONS.items():
        op.bulk_insert(rp, [{"id": uuid.uuid4(), "role_id": role_ids[role], "permission_id": permission_ids[code]} for code in codes])

def downgrade():
    op.drop_index("ix_auth_v2_role_permissions_role_id", table_name="role_permissions", schema=SCHEMA)
    op.drop_table("role_permissions", schema=SCHEMA)
    op.drop_index("ix_auth_v2_user_roles_user_id", table_name="user_roles", schema=SCHEMA)
    op.drop_table("user_roles", schema=SCHEMA)
    op.drop_table("permissions", schema=SCHEMA)
    op.drop_table("roles", schema=SCHEMA)
