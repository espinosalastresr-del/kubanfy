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
    "AuthType",
    "MockProvider",
    "MusicProvider",
    "ProviderCapabilities",
    "ProviderHealth",
    "ProviderHealthStatus",
    "ProviderManager",
    "ProviderRegistry",
    "ResolvedSource",
    "SourceType",
    "TrackMetadata",
    "create_default_registry",
]
