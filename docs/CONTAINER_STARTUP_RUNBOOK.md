# Container startup runbook — kubanfy-api-staging

**Contexto (2026-11-04):** probes externos reciben HTTP 500:

- `The container is not running, consider calling start()`
- `The container just exited`

El dashboard puede reportar instancias “healthy” a nivel de plataforma mientras el proceso FastAPI **muere al arrancar**. Este documento lista lo que hay que verificar **sin inventar la causa**.

Rama de código objetivo: `staging/canonical`.

---

## 1. Síntoma vs sleep

| Observación | Interpretación |
|---|---|
| Instancia `inactive` tras 10m | Normal (`sleepAfter = "10m"`) |
| Primer request tarda y luego 200 | Cold start OK |
| **`just exited`** | El proceso del Container terminó; **no** es solo sleep |
| `not running, consider calling start()` | Worker no pudo obtener un Container vivo |

---

## 2. Cómo obtener evidencia (propietario)

1. Cloudflare Dashboard → Workers → `kubanfy-api-staging` → **Containers / Logs** (o Observability).
2. Generar tráfico: `curl -sS -m 60 https://kubanfy-api-staging.globumlatinmusic.workers.dev/health/live`
3. Capturar **stdout/stderr del Container** en esa ventana (traceback Python, mensaje de uvicorn, OOM).
4. Alternativa CLI (con token local, no en chat):
   - `npx wrangler tail kubanfy-api-staging --format pretty`
   - Revisar logs de build de la imagen Container.

**No pegar en chat:** valores de `DATABASE_URL`, claves JWT/KBY/R2, passwords.

---

## 3. Checklist de causas probables (orden práctico)

### A. Fallo al importar `app.main` (exit inmediato)

- Dockerfile `CMD`: `uvicorn app.main:app ...` → `app = create_app()` corre en import.
- `create_app()` → `get_settings()` → validadores Pydantic.
- En **staging** los guards estrictos de production **no** aplican; un JWT &lt; 32 chars en el secret **sí** tumba el arranque.
- Cualquier excepción en import de routers/schemas tumba el proceso antes de bind al puerto 8000.

### B. Secrets / env incompletos en el Container

Bindings que el Worker **debe** reenviar (ver `infra/cloudflare/api/src/index.ts`):

- `DATABASE_URL`, `DATABASE_URL_SYNC`
- `REDIS_URL`
- `JWT_SECRET_KEY` (≥ 32 caracteres)
- `KBY_MASTER_KEY`
- `OFFLINE_LICENSE_PRIVATE_KEY`, `OFFLINE_LICENSE_PUBLIC_KEY`
- `OFFLINE_LICENSE_ALGORITHM` (ahora reenviado en canónica; default app RS256)
- R2 keys + endpoint + buckets
- `CORS_ORIGINS`, `ALLOWED_HOSTS`

Verificar en dashboard que los **secrets existen** y no están vacíos. Existencia del binding ≠ valor correcto (p. ej. Neon pooled del proyecto `restless-violet-91368868`).

### C. Imagen / healthcheck

- Imagen live (digest): ver deployment Container.
- Dockerfile `HEALTHCHECK` usa `curl` a `/health/live` — si el proceso nunca escucha, healthcheck falla (plataforma puede marcar exit).
- `pingEndpoint` del Container class = `health/live` (sin slash inicial en config Worker).

### D. Red / dependencias en lifespan

- `lifespan`: `init_db` (sync) + `init_redis` (async; warning si falla, no debería matar el proceso).
- Un `DATABASE_URL` inválido suele fallar en **ready**, no necesariamente en live — salvo bug en init.
- Confirmar que el Container tiene `enableInternet = true` (sí en código) para llegar a Neon/Redis/R2.

### E. Discrepancia CORS / ALLOWED_HOSTS en versión desplegada

Repo wrangler (canónica):

- `CORS_ORIGINS=https://kubanfy-web-staging.globumlatinmusic.workers.dev`
- `ALLOWED_HOSTS=kubanfy-api-staging.globumlatinmusic.workers.dev`

Versión live v68 (según propietario): posibles valores **sin** `globumlatinmusic`. Alinear en el próximo deploy.

---

## 4. Qué no hacer hasta tener logs

- No aplicar migración **016** en Neon producción/staging sin aprobación y plan (código canónico la incluye; DB en **015**).
- No redeployar en bucle sin leer el traceback.
- No abrir R2 público ni poner `CORS_ORIGINS=*`.
- No commitear secrets.

---

## 5. Secuencia de recuperación recomendada

1. Logs del exit → causa raíz.  
2. Corregir secret/config/imagen según causa.  
3. (Opcional) Branch Neon de prueba + `alembic upgrade` hasta 016 si se va a desplegar código canónico completo.  
4. Deploy desde `staging/canonical` (Wrangler en `infra/cloudflare/api` o pipeline).  
5. Verificar:
   - `GET /health/live` → 200 `{"status":"ok"}`
   - `GET /health/ready` → 200/503 con checks explícitos (DB/Redis/storage)
   - `GET /openapi.json` en staging
6. Anotar **deployment ID + commit SHA** en `docs/CANONICAL_DEPLOYMENT.md`.

---

## 6. Comandos locales del propietario (referencia)

```bash
# Desde el repo en staging/canonical
cd infra/cloudflare/api
npx wrangler deploy   # requiere CLOUDFLARE_API_TOKEN + account con Containers

# Probe
curl -sS -m 60 https://kubanfy-api-staging.globumlatinmusic.workers.dev/health/live
curl -sS -m 60 https://kubanfy-api-staging.globumlatinmusic.workers.dev/health/ready
```

Migraciones (solo con aprobación):

```bash
# Usar DATABASE_URL_SYNC (host directo Neon), nunca pegar la URL en tickets públicos
alembic upgrade head
```

---

## 7. Estado de esta sesión de auditoría

| Capacidad | Estado |
|---|---|
| Rama canónica + docs + test rutas | Hecho |
| Reenvío `OFFLINE_LICENSE_ALGORITHM` | Hecho en código canónica |
| Lectura de logs Container | **No disponible** sin dashboard/token |
| Deploy | **No ejecutado** |
| Migración 016 | **No ejecutada** |
