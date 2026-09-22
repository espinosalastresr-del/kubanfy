"""External music provider adapters."""

from app.providers.base import (
    AuthType,
    MusicProvider,
    ProviderCapabilities,
    ProviderHealth,
    ProviderHealthStatus,
    ResolvedSource,
    SourceType,
    TrackMetadata,
)
from app.providers.mock import MockProvider
from app.providers.registry import ProviderManager, ProviderRegistry, create_default_registry

__all__ = [
    "MusicProvider",
    "ProviderCapabilities",
    "ProviderHealth",
    "ProviderHealthStatus",
    "ResolvedSource",
    "SourceType",
    "TrackMetadata",
    "AuthType",
    "MockProvider",
    "ProviderRegistry",
    "ProviderManager",
    "create_default_registry",
]
