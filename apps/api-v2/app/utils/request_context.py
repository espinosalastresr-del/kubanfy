import re

from fastapi import Request

from app.core.config import settings


def detected_country(request: Request) -> str | None:
    if not settings.trust_cloudflare_headers:
        return None
    value = request.headers.get("cf-ipcountry", "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", value) or value in {"XX", "T1"}:
        return None
    return value


def client_ip(request: Request) -> str | None:
    if settings.trust_cloudflare_headers:
        value = request.headers.get("cf-connecting-ip")
        return value[:64] if value else None
    return request.client.host[:64] if request.client else None
