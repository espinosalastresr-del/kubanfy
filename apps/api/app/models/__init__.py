"""SQLAlchemy models.

Import all models here so Alembic and metadata see them.
"""

from app.models.device import Device, Session
from app.models.job import Job
from app.models.music import (
    Artist,
    AudioAsset,
    CacheEntry,
    Provider,
    ProviderTrack,
    Release,
    Track,
    TrackArtist,
)
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User

__all__ = [
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
    "Device",
    "Session",
    "Job",
    "Artist",
    "Release",
    "Track",
    "TrackArtist",
    "Provider",
    "ProviderTrack",
    "AudioAsset",
    "CacheEntry",
]
