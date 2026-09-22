"""Development seed data — never use real production data.

Usage:
    cd apps/api && PYTHONPATH=. python -m scripts.seed
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running as module from apps/api
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory, close_db, init_db
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.models.artist_member import ArtistMember, ArtistMemberRole
from app.models.music import Artist, Track, TrackArtist, TrackStatus
from app.models.rbac import SystemRole
from app.models.user import User, UserStatus
from app.services.admin import AdminService
from app.services.entitlement import EntitlementService
from app.services.rbac import RbacService


async def seed() -> None:
    settings = get_settings()
    setup_logging(settings)
    init_db(settings)

    if async_session_factory is None:
        raise RuntimeError("DB not initialized")

    async with async_session_factory() as session:
        rbac = RbacService(session)
        await rbac.ensure_default_rbac()

        admin_svc = AdminService(session)
        await admin_svc.ensure_default_flags()

        ent = EntitlementService(session)
        await ent.ensure_default_plans()

        # Super admin
        admin_email = settings.super_admin_email.lower()
        admin = await session.scalar(select(User).where(User.email == admin_email))
        if admin is None:
            admin = User(
                email=admin_email,
                password_hash=hash_password(settings.super_admin_password),
                display_name="Super Admin",
                country="CU",
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(admin)
            await session.flush()
            await rbac.assign_role(admin.id, SystemRole.SUPER_ADMIN.value)
            print(f"Created super admin: {admin_email}")
        else:
            print(f"Super admin exists: {admin_email}")

        # Demo user
        demo = await session.scalar(select(User).where(User.email == "demo@kubanfy.local"))
        if demo is None:
            demo = User(
                email="demo@kubanfy.local",
                password_hash=hash_password("DemoPass123!"),
                display_name="Demo User",
                country="CU",
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(demo)
            await session.flush()
            print("Created demo user: demo@kubanfy.local / DemoPass123!")

        # Demo artist
        artist = await session.scalar(select(Artist).where(Artist.slug == "buena-vista-demo"))
        if artist is None:
            artist = Artist(
                name="Buena Vista Demo",
                slug="buena-vista-demo",
                bio="Artista de demostración — datos ficticios",
                country="CU",
                status="active",
                verified=True,
            )
            session.add(artist)
            await session.flush()
            if demo:
                session.add(
                    ArtistMember(
                        artist_id=artist.id,
                        user_id=demo.id,
                        role=ArtistMemberRole.OWNER,
                    )
                )
            track = Track(
                title="Guantanamera (Demo)",
                slug="guantanamera-demo",
                duration=180.0,
                status=TrackStatus.PUBLISHED,
                language="es",
            )
            session.add(track)
            await session.flush()
            session.add(
                TrackArtist(track_id=track.id, artist_id=artist.id, role="main", display_order=0)
            )
            print("Created demo artist + track")

        await session.commit()
        print("Seed complete.")

    await close_db()


if __name__ == "__main__":
    asyncio.run(seed())
