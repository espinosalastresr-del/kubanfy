# Staging KubanFy

## Levantar stack

```bash
docker compose -f infrastructure/docker-compose.yml --profile staging up -d --build
```

Servicios:

| Servicio | Puerto | Rol |
|----------|--------|-----|
| postgres | 5432 | DB |
| redis | 6379 | locks / rate limit |
| api | 8000 | FastAPI (migrate + uvicorn) |
| worker | — | jobs TRANSCODE / CACHE_CLEANUP |
| minio | 9000/9001 | S3 local (opcional profile) |

## Comprobar

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
```

El entrypoint del API ejecuta `alembic upgrade head` antes de servir.

## Seed (opcional)

```bash
docker compose -f infrastructure/docker-compose.yml --profile staging exec api \
  python -m scripts.seed
```

## Load smoke

```bash
k6 run -e BASE_URL=http://127.0.0.1:8000 loadtests/k6_smoke.js
```

## Secretos

En staging real sustituir:

- `JWT_SECRET` (≥ 32 chars, aleatorio)
- credenciales DB
- `STORAGE_BACKEND=r2` + keys R2 cuando toque producción

No commitear `.env` con secretos reales.
