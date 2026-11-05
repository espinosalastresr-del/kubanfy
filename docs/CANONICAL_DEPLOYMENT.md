# CANONICAL_DEPLOYMENT — KubanFy staging

**Fecha de actualización:** 2026-11-04  
**Rama canónica de código:** `staging/canonical`  
**HEAD canónico:** `88473d67914b7d1f3b64f424707f0aee08b45f99`  
(origen: `fix/staging-cloudflare-api-origin`)

Regla: solo hechos verificados. Lo no demostrado = `UNKNOWN`.

---

## 1. Decisión de canonicidad (código)

| Campo | Valor |
|---|---|
| Rama canónica | `staging/canonical` |
| SHA | `88473d67914b7d1f3b64f424707f0aee08b45f99` |
| Basada en | `fix/staging-cloudflare-api-origin` |
| Motivo | Más avanzada que `feat/cloudflare-containers-deploy` (26 oct): workflow CF deploy, auth/admin, password reset, email, offline, PWA, **una sola** ruta upload, `PATCH /playlists/{id}/tracks/order`, migración `016_password_reset_tokens` |
| No canónica | `feat/cloudflare-containers-deploy` @ `f68e66a` (upload duplicado; sin order; atrasada) |
| `main` | `f27719e…` — no representa el stack Cloudflare actual |

**Importante:** canónica de **código** ≠ artefacto **desplegado**. El Worker live no expone SHA Git.

---

## 2. Despliegue Cloudflare live (verificado por propietario + probe externo)

### Worker `kubanfy-api-staging`

| Campo | Valor |
|---|---|
| Versión activa | 68 |
| Version ID | `277e6331-abb0-4c0a-8b99-6906bbad1a2d` |
| Deployment ID | `2469e67e-6794-4603-b34a-ef18d81c769b` |
| Fecha | 2026-10-29 11:08 UTC |
| Origen | Wrangler |
| Tráfico | 100 % |
| SHA Git del artefacto | **UNKNOWN** (Cloudflare no lo asocia) |

### Container

| Campo | Valor |
|---|---|
| Imagen | `registry.cloudflare.com/.../kubanfy-api-staging-kubanfyapicontainer@sha256:4b682030…` |
| Instancias fallidas (dashboard) | 0 |
| Salud reportada (dashboard) | 3 healthy |
| Instancia `staging-api` | inactive (coherente con `sleepAfter=10m`); actualizada ~2026-11-04 07:17 UTC |

### Probe externo (2026-11-04)

```text
GET /health/live  → 500  "Failed to start container: The container is not running"
GET /health       → 500  "Failed to start container: The container just exited"
```

Interpretación: no es solo sleep. El Container **intenta arrancar y termina** (exit). Causa exacta = **UNKNOWN** sin logs internos del proceso.

### Web staging

- URL: `https://kubanfy-web-staging.globumlatinmusic.workers.dev` — HTTP 200 observado.

### Discrepancia de configuración

Versión activa del Worker: `ALLOWED_HOSTS` / `CORS_ORIGINS` con dominios `.workers.dev` **sin** el host `globumlatinmusic` que aparece en configs del repo. Verificar si es intencional antes de asumir CORS correcto.

---

## 3. Neon

| Campo | Valor |
|---|---|
| Proyecto | KubanFy / `restless-violet-91368868` (handoff) |
| `alembic_version` | **015** |
| Migración en código canónico | `016_password_reset_tokens` presente en árbol de `staging/canonical` |
| Estado | **016 no aplicada** en el endpoint inspeccionado |

**Política:** no ejecutar migraciones ni DDL sin aprobación explícita del propietario. Desplegar código canónico sin 016 puede romper password-reset u otros paths que dependan de la tabla nueva.

---

## 4. Arquitectura objetivo (sin cambios)

```text
Browser / PWA
  → Worker Static Assets (kubanfy-web-staging)
  → Worker API (kubanfy-api-staging)
  → Container FastAPI :8000
       → Neon (DATABASE_URL pooled)
       → Redis
       → R2 signed
```

No Render / D1 / SQLite como backend de aplicación.

---

## 5. Acciones completadas en esta auditoría

1. Rama `staging/canonical` creada desde `fix/staging-cloudflare-api-origin` @ `88473d6`.
2. Documentación de despliegue y contrato API actualizada en esta rama.
3. Test de unicidad de rutas HTTP (`apps/api/tests/test_route_uniqueness.py`) para evitar regresión del doble upload de `feat`.

## 6. Acciones **no** realizadas (bloqueadas o sin capacidad)

| Acción | Motivo |
|---|---|
| Deploy Wrangler / Workers Builds | Sin token Cloudflare en esta sesión; Container en exit |
| Aplicar Alembic 016 en Neon | Requiere aprobación explícita; Neon en 015 |
| Atribuir SHA Git al deploy del 29 oct | Cloudflare no lo expone |
| Declarar API “healthy” | Probe externo 500 / just exited |

---

## 7. Checklist para el propietario (deploy seguro)

1. **Logs del Container** al forzar un request (traceback del exit).  
2. Corregir causa del exit (secret, import, DB connect on startup, puerto, imagen).  
3. **Aprobar o rechazar** aplicación de migración 016 (preferible branch Neon de prueba primero).  
4. Deploy desde `staging/canonical` (HEAD actual o commit posterior de esta rama) con workflow CF / Wrangler.  
5. Verificar:
   - `GET /health/live` → 200  
   - `GET /health/ready` → 200  
   - CORS origen web staging  
   - OpenAPI `/openapi.json` accesible en staging  
6. Registrar en este documento: **SHA Git del artefacto desplegado** + deployment ID nuevo.  
7. Solo entonces continuar features PWA contra API real.

---

## 8. URLs

| Servicio | URL |
|---|---|
| API staging | `https://kubanfy-api-staging.globumlatinmusic.workers.dev` |
| Web staging | `https://kubanfy-web-staging.globumlatinmusic.workers.dev` |
| Rama canónica | https://github.com/espinosalastresr-del/kubanfy/tree/staging/canonical |

**Prioridad:** exactitud > seguridad > robustez > velocidad.
