"""Explicit, environment-gated bootstrap for a first KubanFy administrator.

Run from apps/api-v2 after applying Alembic 0003:
KUBANFY_BOOTSTRAP_ADMIN_ENABLED=1 KUBANFY_BOOTSTRAP_ADMIN_EMAIL=... \
KUBANFY_BOOTSTRAP_ADMIN_PASSWORD=... python -m scripts.bootstrap_admin

Never store bootstrap credentials in source control or logs.
"""
import asyncio
import os
from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import normalize_async_database_url, settings
from app.core.security import hash_password
from app.models import Role, User, UserRole

async def main() -> None:
    if os.getenv("KUBANFY_BOOTSTRAP_ADMIN_ENABLED") != "1":
        raise SystemExit("Bootstrap disabled. Set KUBANFY_BOOTSTRAP_ADMIN_ENABLED=1 explicitly.")
    email = os.getenv("KUBANFY_BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("KUBANFY_BOOTSTRAP_ADMIN_PASSWORD", "")
    full_name = os.getenv("KUBANFY_BOOTSTRAP_ADMIN_NAME", "KubanFy Test Administrator").strip()
    age = int(os.getenv("KUBANFY_BOOTSTRAP_ADMIN_AGE", "30"))
    country = os.getenv("KUBANFY_BOOTSTRAP_ADMIN_COUNTRY", "CU").strip().upper()
    if not email or len(password) < 20:
        raise SystemExit("Provide an admin email and a bootstrap password of at least 20 characters.")
    if len(country) != 2 or not country.isalpha() or not 1 <= age <= 120:
        raise SystemExit("Admin country must be ISO alpha-2 and age between 1 and 120.")
    engine = create_async_engine(normalize_async_database_url(settings.database_url), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        admin_role = await db.scalar(select(Role).where(Role.name == "admin"))
        if admin_role is None:
            raise SystemExit("RBAC schema/seed missing. Run Alembic upgrade head first.")
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                full_name=full_name, age=age, email=email, password_hash=hash_password(password),
                country_of_origin=country, accepted_terms_version=settings.terms_version,
                accepted_terms_at=datetime.now(UTC), is_active=True,
            )
            db.add(user)
            await db.flush()
        existing = await db.scalar(select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == admin_role.id))
        if existing is None:
            db.add(UserRole(user_id=user.id, role_id=admin_role.id))
        await db.commit()
        print(f"Administrator role provisioned for {email}. Use the normal login endpoint.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
