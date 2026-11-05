"""Async SQLAlchemy engine and session management.

PostgreSQL is the source of truth. Redis is never used as source of truth.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings, get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


def normalize_asyncpg_url(database_url: str) -> str:
    """Return a SQLAlchemy URL suitable for the asyncpg dialect.

    - Rewrites ``postgresql://`` / ``postgres://`` to ``postgresql+asyncpg://``.
    - Converts query param ``sslmode`` → ``ssl`` (same value) because asyncpg
      rejects the libpq-style ``sslmode`` keyword.
    - Does not mutate the original settings value; call sites pass a copy.
    - Leaves ``ssl`` untouched if already present; drops redundant ``sslmode``.
    - Preserves all other query parameters.

    Sync / psycopg URLs (``DATABASE_URL_SYNC``) must NOT be passed through this
    helper so that ``sslmode`` remains valid for libpq-based drivers.
    """
    url = database_url
    if url.startswith("postgresql+asyncpg://"):
        pass
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    elif url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql+psycopg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql+psycopg://") :]
    elif url.startswith("postgresql+psycopg2://"):
        url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://") :]

    parsed = urlparse(url)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    sslmode_value: str | None = None
    has_ssl = False
    new_pairs: list[tuple[str, str]] = []
    for key, value in pairs:
        lowered = key.lower()
        if lowered == "sslmode":
            sslmode_value = value
            continue
        if lowered == "ssl":
            has_ssl = True
        new_pairs.append((key, value))

    if sslmode_value is not None and not has_ssl:
        new_pairs.append(("ssl", sslmode_value))

    return urlunparse(parsed._replace(query=urlencode(new_pairs)))


def create_engine(settings: Settings | None = None) -> Any:
    settings = settings or get_settings()
    # Normalize a derived URL only; never write back to settings.database_url.
    database_url = normalize_asyncpg_url(settings.database_url)

    return create_async_engine(
        database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        echo=settings.db_echo,
        pool_pre_ping=True,
    )


# Module-level engine/session factory — initialized in lifespan
engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: Settings | None = None) -> None:
    """Initialize engine and session factory. Called from app lifespan."""
    global engine, async_session_factory
    settings = settings or get_settings()
    engine = create_engine(settings)
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def close_db() -> None:
    """Dispose engine. Called on shutdown."""
    global engine, async_session_factory
    if engine is not None:
        await engine.dispose()
        engine = None
        async_session_factory = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
