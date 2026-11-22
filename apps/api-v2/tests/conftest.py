import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models import Base, Permission, Role, RolePermission

settings.cookie_secure = False

@pytest.fixture
async def client():
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE SCHEMA IF NOT EXISTS auth_v2"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as seed:
        roles = {name: Role(name=name, description=f"Test role {name}") for name in ("free", "premium", "artist", "admin")}
        permission = Permission(code="admin.dashboard.access", description="Admin dashboard access")
        seed.add_all([*roles.values(), permission])
        await seed.flush()
        seed.add(RolePermission(role=roles["admin"], permission=permission))
        await seed.commit()
    async def override_db():
        async with factory() as session:
            yield session
    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("DROP SCHEMA IF EXISTS auth_v2"))
    await engine.dispose()
