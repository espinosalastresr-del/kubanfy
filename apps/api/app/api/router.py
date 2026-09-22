"""Root API router. Aggregates all versioned sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.music import router as music_router

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
