# API review notes — staging/canonical (2026-11-04)

## Correcciones aplicadas en código

1. **Migración 016 + password reset** portados desde `feat` (faltaban en canónica).
2. **EmailDeliveryService**: provider `CONSOLE` ya no lanza error; registra recipient/subject sin cuerpo (evita invalidar tokens y filtrar enlaces en logs).
3. **`frontend_base_url`** (config) para enlaces de reset — aplicar en commit de config si aún no está.
4. **`PATCH /auth/me`** y endpoints password-reset (auth.py).
5. Tests de unicidad de rutas y password-reset.
6. **OFFLINE_LICENSE_ALGORITHM** reenviado al Container.

## Hallazgos (sin cambio de código o diferidos)

| Hallazgo | Severidad | Acción |
|---|---|---|
| Container live `just exited` | P0 ops | Runbook; logs + redeploy propietario |
| Código muerto tras raise 410 en `/music/content` | Baja | Cosmético |
| `app = create_app()` en import | Media | Fallos de Settings tumba el proceso |
| JWT secret débil/ausente en CF | Alta ops | Verificar secret ≥ 32 chars |
| OpenAPI no verificable live | Bloqueo | Hasta health 200 |

## No hecho en esta sesión

- Deploy Cloudflare
- `alembic upgrade` en Neon (sin credenciales aquí) — ver `docs/APPLY_MIGRATION_016.md`
