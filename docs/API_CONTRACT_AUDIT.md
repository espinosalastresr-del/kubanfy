# API_CONTRACT_AUDIT — KubanFy

**Fecha:** 2026-11-04  
**Código canónico:** rama `staging/canonical` @ `88473d67914b7d1f3b64f424707f0aee08b45f99` (desde `fix/staging-cloudflare-api-origin`)  
**Contraste histórico:** `feat/cloudflare-containers-deploy` @ `f68e66ab540002cd58b70a7ce9594340f73162ac`  
**Prefijo API:** `/v1`  
**OpenAPI live staging:** no disponible (Container exit / 500). No se simula OpenAPI.

**Leyenda Auth:** Pública | OptionalUser | Bearer (CurrentUser) | RBAC (`require_permissions`)

---

## Agregación

`apps/api/app/api/router.py` incluye: auth, music, offline, artists, library, payments, discovery, entitlements, analytics, admin + `GET /`.

---

## Auth — prefix `/auth`

| Método | Ruta | Auth | Notas |
|---|---|---|---|
| POST | `/v1/auth/register` | Pública | 201 |
| POST | `/v1/auth/login` | Pública | |
| POST | `/v1/auth/password-reset/request` | Pública | 202; canónica incluye flujo tokens (migración 016) |
| POST | `/v1/auth/password-reset/confirm` | Pública | |
| POST | `/v1/auth/refresh` | body refresh | |
| GET/PATCH | `/v1/auth/me` | Bearer | |
| GET | `/v1/auth/context` | Bearer | |
| GET/DELETE | `/v1/auth/devices…` | Bearer | |
| GET/DELETE | `/v1/auth/sessions…` | Bearer | |
| POST | `/v1/auth/logout-all` | Bearer | 204 |

Schemas: `apps/api/app/schemas/auth.py`.

---

## Music — prefix `/music`

| Método | Ruta | Auth | Notas críticas |
|---|---|---|---|
| POST | `/v1/music/update` | OptionalUser | |
| POST | `/v1/music/preview` | OptionalUser | |
| GET | `/v1/music/tracks/{track_id}` | OptionalUser | Metadata; usar para resolver playlist tracks |
| GET | `/v1/music/play/{track_id}` | Bearer | **Playback canónico** — quality, kby_version 1–2 (cliente web pide 2) → signed R2 + kby_key |
| POST | `/v1/music/download` | Bearer + entitlement | offline license |
| GET | `/v1/music/offline/bootstrap` | Bearer | limit 1–3; X-Device-ID |
| GET | `/v1/music/search` | Pública | q, limit |
| GET | `/v1/music/local-delivery/{token}` | token | solo LocalStorage |
| GET | `/v1/music/content/{track_id}` | Bearer | **HTTP 410** — no usar en PWA |

---

## Offline — prefix `/offline`

| Método | Ruta | Auth |
|---|---|---|
| GET | `/v1/offline/licenses/public-key` | Pública |
| POST | `/v1/offline/licenses/validate` | Bearer |

---

## Library — sin prefix de router (bajo `/v1`)

| Método | Ruta | Auth | Canónica |
|---|---|---|---|
| CRUD playlists | `/v1/playlists…` | Bearer / OptionalUser en GET por id | sí |
| add/remove track | `/v1/playlists/{id}/tracks/{track_id}` | Bearer | sí |
| GET tracks | `/v1/playlists/{id}/tracks` | OptionalUser | IDs + position; no metadata completa |
| **PATCH order** | `/v1/playlists/{id}/tracks/order` | Bearer | **sí en canónica**; no en `feat` |
| favorites | `/v1/favorites…` | Bearer | sí |
| GET | `/v1/entitlements` | Bearer | también `/entitlements/me` |

---

## Entitlements / Discovery / Analytics / Payments / Admin

Ver handoff y routers en SHA canónico. Resumen:

- `GET /v1/entitlements/me` — Bearer  
- Discovery: `/home`, `/local-artists`, `/top50`, `/new-releases`  
- Analytics: events, playback start/heartbeat (interval 10s, qualify 30s), downloads ticket/complete, shares  
- Payments: create/list/submit + admin approve/reject (RBAC)  
- Admin: feature-flags, settings, moderation, users/plan, suspend, audit-logs, rbac ensure-defaults  

---

## Artist — prefix `/artist`

Upload: **una sola** `POST /v1/artist/{artist_id}/tracks/upload` en canónica.  
En `feat` había **dos** registros de la misma ruta (regresión cubierta por `test_route_uniqueness.py`).

---

## Health (fuera de `/v1`)

`/health`, `/health/live`, `/health/ready`, `/metrics`, `/docs`, `/openapi.json` (staging).

Live al 2026-11-04: **500** por Container exit.

---

## Cliente PWA (`apps/web/src/api.ts`)

Base default: `https://kubanfy-api-staging.globumlatinmusic.workers.dev`  
Headers: Accept, X-KubanFy-Platform: web, X-Device-ID, Bearer si hay token.  
Retry solo lecturas idempotentes.

---

## Divergencias feat vs canónica (recordatorio)

| Ítem | feat | staging/canonical |
|---|---|---|
| Upload tracks | duplicado | único |
| Playlist order | no | sí |
| Migración 016 | no | sí (código; Neon aún 015) |

---

## Próximo paso de contrato

Cuando `/health/live` sea 200: descargar `/openapi.json` y diff contra esta tabla. No declarar integración completa sin ese cotejo.
