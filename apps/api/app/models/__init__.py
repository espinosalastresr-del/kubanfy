"""SQLAlchemy models.

Import all models here so Alembic and metadata see them.
"""

from app.models.analytics import AnalyticsDaily, AnalyticsEvent, RankingSnapshot
from app.models.artist_member import ArtistMember
from app.models.device import Device, Session
from app.models.entitlement import Entitlement, Plan, PlanPrice, Subscription
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
from app.models.payment import PaymentOrder
from app.models.playlist import Favorite, Playlist, PlaylistTrack
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.rights import LicenseRecord
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
    "ArtistMember",
    "LicenseRecord",
    "Playlist",
    "PlaylistTrack",
    "Favorite",
    "Plan",
    "PlanPrice",
    "Subscription",
    "Entitlement",
    "PaymentOrder",
    "AnalyticsEvent",
    "AnalyticsDaily",
    "RankingSnapshot",
]
