"""Async SQLAlchemy engine and session management.

PostgreSQL is the source of truth. Redis is never used as source of truth.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

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


def create_engine(settings: Settings | None = None) -> Any:
    settings = settings or get_settings()
    return create_async_engine(
        settings.database_url,
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
