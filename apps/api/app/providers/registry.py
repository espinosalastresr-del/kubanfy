"""Provider registry and manager.

Never couple MusicEngine to a concrete provider.
Selection uses priority, health, capabilities — never if provider == "x".
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.providers.base import (
    MusicProvider,
    ProviderHealth,
    ProviderHealthStatus,
    ResolvedSource,
    TrackMetadata,
)
from app.providers.mock import MockProvider

logger = get_logger(__name__)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, MusicProvider] = {}

    def register(self, provider: MusicProvider) -> None:
        self._providers[provider.name] = provider
        logger.info("provider_registered", name=provider.name, priority=provider.priority)

    def get(self, name: str) -> MusicProvider | None:
        return self._providers.get(name)

    def list_providers(self) -> list[MusicProvider]:
        return sorted(self._providers.values(), key=lambda p: p.priority)

    def available(self) -> list[MusicProvider]:
        return [p for p in self.list_providers() if p.is_available()]


class ProviderManager:
    """Facade used by MusicEngine."""

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self.registry = registry or ProviderRegistry()

    async def search(
        self,
        query: str,
        *,
        limit: int = 20,
        provider_name: str | None = None,
    ) -> list[tuple[str, TrackMetadata]]:
        """Search across providers. Returns (provider_name, metadata) pairs."""
        results: list[tuple[str, TrackMetadata]] = []
        providers = (
            [self.registry.get(provider_name)]
            if provider_name
            else self.registry.available()
        )
        for provider in providers:
            if provider is None:
                continue
            try:
                tracks = await provider.search(query, limit=limit)
                for t in tracks:
                    results.append((provider.name, t))
            except Exception as exc:
                logger.warning(
                    "provider_search_failed",
                    provider=provider.name,
                    error=str(exc),
                )
        return results[:limit]

    async def get_track(
        self,
        provider_name: str,
        provider_track_id: str,
    ) -> TrackMetadata | None:
        provider = self.registry.get(provider_name)
        if provider is None or not provider.is_available():
            return None
        return await provider.get_track(provider_track_id)

    async def resolve(
        self,
        provider_name: str,
        provider_track_id: str,
        *,
        quality: str = "medium",
    ) -> ResolvedSource | None:
        provider = self.registry.get(provider_name)
        if provider is None or not provider.is_available():
            return None
        return await provider.resolve(provider_track_id, quality=quality)

    async def preview(
        self,
        provider_name: str,
        provider_track_id: str,
    ) -> ResolvedSource | None:
        provider = self.registry.get(provider_name)
        if provider is None or not provider.is_available():
            return None
        return await provider.preview(provider_track_id)

    async def health_all(self) -> dict[str, ProviderHealth]:
        out: dict[str, ProviderHealth] = {}
        for p in self.registry.list_providers():
            if not p.is_available():
                out[p.name] = ProviderHealth(
                    status=ProviderHealthStatus.UNAVAILABLE,
                    message="Missing credentials or disabled",
                )
                continue
            try:
                out[p.name] = await p.health_check()
            except Exception as exc:
                out[p.name] = ProviderHealth(
                    status=ProviderHealthStatus.OFFLINE,
                    message=str(exc),
                )
        return out

    def resolve_with_fallback(
        self,
        candidates: list[tuple[str, str]],
        *,
        quality: str = "medium",
    ) -> Any:
        """Placeholder for ordered fallback resolution (async in MusicEngine)."""
        return candidates


def create_default_registry(*, include_mock: bool = True) -> ProviderRegistry:
    registry = ProviderRegistry()
    if include_mock:
        registry.register(MockProvider())
    return registry
