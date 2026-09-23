"""SQLAlchemy models.

Import all models here so Alembic and metadata see them.
"""

from app.models.admin import AuditLog, FeatureFlag, ModerationReport, SystemSetting
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
from app.models.offline import OfflineLicense
from app.models.payment import PaymentOrder
from app.models.playlist import Favorite, Playlist, PlaylistTrack
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.rights import (
    CollaboratorSplit,
    LicenseRecord,
    RoyaltyAccount,
    RoyaltyLedgerEntry,
    RoyaltySettlement,
)
from app.models.user import User

__all__ = [
    "AnalyticsDaily",
    "AnalyticsEvent",
    "Artist",
    "ArtistMember",
    "AudioAsset",
    "AuditLog",
    "CacheEntry",
    "CollaboratorSplit",
    "Device",
    "Entitlement",
    "Favorite",
    "FeatureFlag",
    "Job",
    "LicenseRecord",
    "ModerationReport",
    "OfflineLicense",
    "PaymentOrder",
    "Permission",
    "Plan",
    "PlanPrice",
    "Playlist",
    "PlaylistTrack",
    "Provider",
    "ProviderTrack",
    "RankingSnapshot",
    "Release",
    "Role",
    "RolePermission",
    "RoyaltyAccount",
    "RoyaltyLedgerEntry",
    "RoyaltySettlement",
    "Session",
    "Subscription",
    "SystemSetting",
    "Track",
    "TrackArtist",
    "User",
    "UserRole",
]
