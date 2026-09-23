"""Transfer external resolved audio sources into KubanFy storage.

Provider URLs are temporary acquisition inputs only. This service never returns
provider URLs to API clients.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.core.exceptions import ProviderUnavailableError
from app.providers.base import ResolvedSource


class TransferManager:
    """Download a resolved provider source for internal storage."""

    def __init__(self, *, timeout_seconds: float = 60.0, max_size_mb: int = 500) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def acquire(self, source: ResolvedSource) -> bytes:
        if source.body is not None:
            return bytes(source.body)

        if source.url is None:
            raise ProviderUnavailableError("Resolved source has no transferable body or URL")

        if not source.url.lower().startswith("https://"):
            raise ProviderUnavailableError("Provider source must use HTTPS")

        if source.expiry is not None:
            remaining = (source.expiry - datetime.now(UTC)).total_seconds()
            if remaining <= 0:
                raise ProviderUnavailableError("Resolved provider source has expired")
            timeout = min(self.timeout_seconds, max(5.0, remaining))
        else:
            timeout = self.timeout_seconds

        timeout_cfg = httpx.Timeout(timeout)
        try:
            async with httpx.AsyncClient(
                timeout=timeout_cfg,
                follow_redirects=False,
            ) as client:
                async with client.stream("GET", source.url, headers=source.headers) as response:
                    response.raise_for_status()
                    length = response.headers.get("content-length")
                    if length and int(length) > self.max_size_bytes:
                        raise ProviderUnavailableError("Resolved source exceeds transfer size limit")

                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > self.max_size_bytes:
                            raise ProviderUnavailableError(
                                "Resolved source exceeds transfer size limit"
                            )
                        chunks.append(chunk)
                    return b"".join(chunks)
        except ProviderUnavailableError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailableError("Provider source transfer failed") from exc
