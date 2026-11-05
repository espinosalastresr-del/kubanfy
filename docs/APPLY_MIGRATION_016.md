# Aplicar migración 016 en Neon (staging)

**Autorización del propietario:** 2026-11-04 — aplicar 016.

Esta sesión de Grok **no tiene** `DATABASE_URL` / `DATABASE_URL_SYNC` y **no puede** ejecutar DDL en tu proyecto Neon. El código de la migración ya está en `staging/canonical`. Tú (o CI) debéis aplicar el esquema.

## Qué hace 016

Crea la tabla `password_reset_tokens` (tokens hasheados, con expiración y uso único) para:

- `POST /v1/auth/password-reset/request`
- `POST /v1/auth/password-reset/confirm`

## Precondiciones

1. Neon en `alembic_version = 015` (o inferior, subiendo en orden).
2. Código en `staging/canonical` con `016_password_reset_tokens.py`.
3. `DATABASE_URL_SYNC` = host **directo** Neon (sin `-pooler`).

## Comando (en máquina con secretos, no en chat)

```bash
cd apps/api
export DATABASE_URL_SYNC="postgresql://..."   # host directo, no pegar aquí
alembic upgrade head
# Verificar: SELECT version_num FROM alembic_version;  -- debe ser 016
```

Preferible: branch Neon de prueba primero, validar, luego el endpoint principal.

## Tras aplicar

1. Redeploy Worker/Container desde `staging/canonical`.
2. Probar password-reset (respuesta genérica 202).
3. Confirmar provider de email (CONSOLE no loguea el token en claro en el body).
