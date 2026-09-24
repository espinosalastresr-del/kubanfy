# KubanFy

Plataforma de música orientada al mercado cubano. Offline-first, optimizada para conexiones lentas e inestables, con catálogo de artistas locales e independientes y arquitectura preparada para monetización futura.

> **Estado**: desarrollo activo según el Plan Técnico Completo.

## Arquitectura (resumen)

```
kubanfy/
  apps/
    api/          # FastAPI backend
    android/      # Android nativo (Kotlin)
    ios/          # iOS nativo (Swift/SwiftUI)
    admin/        # (opcional) panel web futuro
    artist/       # (opcional) portal web futuro
  packages/
    contracts/    # Shared OpenAPI / TypeScript contracts
    shared/       # Shared utilities
  workers/        # Background workers
  infrastructure/ # Docker, Terraform, etc.
  scripts/
  docs/
  tests/
```

## Stack principal

| Capa            | Tecnología                          |
|-----------------|-------------------------------------|
| Backend         | Python 3.12+, FastAPI, Pydantic v2  |
| ORM             | SQLAlchemy 2.x + Alembic            |
| Base de datos   | PostgreSQL                          |
| Cache / colas   | Redis                               |
| Storage         | Cloudflare R2                       |
| Audio           | FFmpeg / FFprobe                    |
| Mobile          | Android Kotlin + iOS Swift/SwiftUI   |
| Admin / Artist  | Next.js + TypeScript                |

## Requisitos de desarrollo

- Python ≥ 3.12
- Node.js ≥ 20
- PostgreSQL ≥ 16
- Redis ≥ 7
- FFmpeg
- Docker + Docker Compose (recomendado)

## Inicio rápido (desarrollo)

```bash
# 1. Clonar e instalar
cp .env.example .env
# Editar .env con valores locales

# 2. Con Docker Compose (recomendado)
make dev

# 3. Sin Docker (solo API + dependencias externas)
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Comandos útiles

```bash
make dev          # Levanta todo el stack de desarrollo
make test         # Tests
make lint         # Linters
make format       # Formatters
make migrate      # Ejecutar migraciones
make seed         # Datos de desarrollo
make worker       # Worker de background
make api          # Solo API
```

## Operaciones (API)

| Endpoint | Uso |
|----------|-----|
| `GET /health/live` | Liveness (K8s) |
| `GET /health/ready` | Readiness (DB, Redis, storage) |
| `GET /health` | Versión y entorno |
| `GET /metrics` | Prometheus scrape |
| `GET /docs` | OpenAPI (no producción) |

Headers de respuesta: `X-Request-ID`, `X-Correlation-ID`.

CI: GitHub Actions (`.github/workflows/ci.yml`) — pytest + Alembic + build Docker.

## Documentación

- [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [API.md](docs/API.md)
- [PROVIDERS.md](docs/PROVIDERS.md)
- [SECURITY.md](docs/SECURITY.md)
- [DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [CONTRIBUTING.md](docs/CONTRIBUTING.md)

## Principios

1. Seguridad antes que comodidad
2. Integridad antes que velocidad
3. Cache antes que adquisición externa
4. No acoplar proveedores
5. No confiar en el cliente para autorización
6. Diseñar para conexiones malas y fallos

## Licencia

Propietario — todos los derechos reservados.
