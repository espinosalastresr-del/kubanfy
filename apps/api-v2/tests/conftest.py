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
        roles = {
            name: Role(name=name, description=f"Test role {name}")
            for name in ("free", "premium", "artist", "admin")
        }
        permission_definitions = {
            "account.self.read": "Consultar el propio perfil",
            "music.stream": "Reproducir música",
            "playlist.manage.self": "Administrar listas propias",
            "premium.offline.download": "Descargas offline premium",
            "artist.catalog.manage": "Administrar catálogo de artista",
            "artist.analytics.read": "Consultar estadísticas de artista",
            "admin.dashboard.access": "Acceder al panel administrativo",
            "admin.users.manage": "Administrar usuarios",
            "admin.roles.manage": "Administrar roles y permisos",
            "admin.catalog.manage": "Administrar catálogo global",
            "admin.platform.settings": "Administrar configuración de plataforma",
            "admin.audit.read": "Consultar auditoría",
        }
        permissions = {
            code: Permission(code=code, description=description)
            for code, description in permission_definitions.items()
        }
        role_permissions = {
            "free": ("account.self.read", "music.stream", "playlist.manage.self"),
            "premium": (
                "account.self.read",
                "music.stream",
                "playlist.manage.self",
                "premium.offline.download",
            ),
            "artist": (
                "account.self.read",
                "music.stream",
                "playlist.manage.self",
                "artist.catalog.manage",
                "artist.analytics.read",
            ),
            "admin": tuple(permission_definitions),
        }
        seed.add_all([*roles.values(), *permissions.values()])
        await seed.flush()
        seed.add_all(
            [
                RolePermission(role=roles[role_name], permission=permissions[code])
                for role_name, codes in role_permissions.items()
                for code in codes
            ]
        )
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
