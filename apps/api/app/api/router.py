"""Root API router. Aggregates all versioned sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.artists import router as artists_router
from app.api.v1.auth import router as auth_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.library import router as library_router
from app.api.v1.music import router as music_router
from app.api.v1.payments import router as payments_router

api_router = APIRouter()


@api_router.get("/", tags=["root"])
async def api_root() -> dict[str, str]:
    return {
        "message": "KubanFy API v1",
        "docs": "/docs",
        "health": "/health",
    }


api_router.include_router(auth_router)
api_router.include_router(music_router)
api_router.include_router(artists_router)
api_router.include_router(library_router)
api_router.include_router(payments_router)
api_router.include_router(discovery_router)
api_router.include_router(analytics_router)
