"""Geolocation by IP — never trust client-sent country.

Server determines country from IP. Fallback: user-selected or default CU.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GeoResult:
    country: str
    region: str | None = None
    source: str = "default"  # inferred | user_selected | default


class GeoService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._reader = None
        if self.settings.geoip_db_path:
            try:
                import geoip2.database

                self._reader = geoip2.database.Reader(self.settings.geoip_db_path)
                logger.info("geoip_db_loaded", path=self.settings.geoip_db_path)
            except Exception as exc:
                logger.warning("geoip_db_load_failed", error=str(exc))

    def resolve_client_ip(
        self,
        request_ip: str | None,
        *,
        cf_connecting_ip: str | None = None,
        forwarded_for: str | None = None,
    ) -> str | None:
        """Resolve the edge client IP and trust forwarded hops only from known proxies."""
        if cf_connecting_ip:
            try:
                return str(ip_address(cf_connecting_ip.strip()))
            except ValueError:
                logger.warning("invalid_cf_connecting_ip")

        trusted = self.settings.trusted_proxy_ip_list
        if forwarded_for and request_ip and request_ip in trusted:
            for candidate in forwarded_for.split(","):
                candidate = candidate.strip()
                if not candidate:
                    continue
                try:
                    return str(ip_address(candidate))
                except ValueError:
                    continue
        return request_ip

    def country_from_ip(self, ip: str | None) -> GeoResult:
        default = self.settings.default_country.upper()
        if not ip or ip in ("127.0.0.1", "::1", "localhost"):
            return GeoResult(country=default, source="default")

        if self._reader is not None:
            try:
                resp = self._reader.country(ip)
                code = (resp.country.iso_code or default).upper()
                return GeoResult(country=code, source="inferred")
            except Exception:
                pass

        # Without GeoIP DB, cannot infer — use default (never trust client)
        return GeoResult(country=default, source="default")

    def resolve(
        self,
        *,
        ip: str | None = None,
        user_selected_country: str | None = None,
    ) -> GeoResult:
        if user_selected_country and len(user_selected_country) == 2:
            return GeoResult(
                country=user_selected_country.upper(),
                source="user_selected",
            )
        return self.country_from_ip(ip)
