"""Alembic environment for KubanFy.

Uses the configured PostgreSQL URL and normalizes Render's postgres:///
postgresql:// connection strings to the asyncpg SQLAlchemy dialect.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.database import Base

# Import all models so metadata is populated
from app.models import (  # noqa: F401
    AnalyticsDaily, AnalyticsEvent, Artist, ArtistMember, AudioAsset, AuditLog,
    CacheEntry, Device, Entitlement, Favorite, FeatureFlag, Job, LicenseRecord,
    ModerationReport, PaymentOrder, Permission, Plan, PlanPrice, Playlist,
    PlaylistTrack, Provider, ProviderTrack, RankingSnapshot, Release, Role,
    RolePermission, Session, Subscription, SystemSetting, Track, TrackArtist,
    User, UserRole,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = "postgresql+asyncpg://" + database_url[len("postgresql://"):]
elif database_url.startswith("postgres://"):
    database_url = "postgresql+asyncpg://" + database_url[len("postgres://"):]
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_type=True,
                      compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata,
                      compare_type=True, compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
