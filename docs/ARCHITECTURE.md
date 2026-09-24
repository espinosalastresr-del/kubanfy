# Arquitectura de KubanFy

## Visión general

KubanFy es un monolito modular + workers. No se introducen microservicios innecesarios en la fase inicial.

```
Cliente (App móvil unificada: listener + artist + admin)
          |
          v
       FastAPI (/v1)
          |
    +-----+-----+-----+-----+
    |     |     |     |     |
  Auth  Music Artist Discovery ...
    |     |     |     |
    v     v     v     v
       PostgreSQL  (source of truth)
          |
       Redis       (locks, queues, rate limits, temporary state)
          |
       Workers     (acquisition, FFmpeg, analytics, rankings, cleanup)
          |
       Cloudflare R2
         - kubanfy-cache/      (temporal)
         - kubanfy-permanent/  (catálogo de artistas)
```


## Cliente móvil unificado

El cliente se implementa como aplicaciones nativas por plataforma: Kotlin en Android y Swift/SwiftUI en iOS. Ambas atienden:

- **Listener** — todos los usuarios autenticados
- **Artist** — roles ARTIST / ARTIST_MANAGER
- **Admin** — roles de operación (SUPER_ADMIN, ADMIN, MODERATOR, …)

El conmutador de modo es solo UI. **La autorización real es del API** (JWT + RBAC + audit).
No se confía en el cliente para roles, país ni entitlements.

Builds de release: GitHub Actions → APK (Android) e IPA (iOS), con CI separado por plataforma.

## Principios

1. Seguridad antes que comodidad
2. Integridad antes que velocidad
3. Cache antes que adquisición externa
4. Single-flight para evitar stampede
5. Proveedores desacoplados vía ProviderManager
6. Entitlements separados de pagos
7. Offline-first (cache ≠ download)
8. TLS obligatorio hacia proveedores externos
9. No confiar en el cliente para autorización, país o roles
10. Valores comerciales siempre configurables

## Capas del backend

| Capa            | Responsabilidad                                      |
|-----------------|------------------------------------------------------|
| `api/`          | Rutas HTTP, validación de entrada, serialización     |
| `schemas/`      | Pydantic request/response                            |
| `services/`     | Lógica de negocio                                    |
| `repositories/` | Acceso a datos (cuando el servicio crezca)           |
| `models/`       | SQLAlchemy ORM                                       |
| `domain/`       | Entidades / value objects puros (cuando aplique)     |
| `providers/`    | Adaptadores de proveedores de música                 |
| `storage/`      | Abstracción R2 / object storage                      |
| `security/`     | AuthZ, anti-abuso, device binding                    |
| `workers/`      | Jobs asíncronos                                      |
| `core/`         | Config, DB, Redis, logging, excepciones              |

## Music Engine (flujo conceptual)

```
update()   → resolver metadata sin obligar descarga
preview()  → preview oficial o muestra legal/cacheada
download() → auth → entitlement → cache lookup
               HIT  → R2 signed URL (.kby) + authorized KBY key
               MISS → ProviderManager → acquire → validate
                     → encrypt/package .kby → store → transcode
                     → encrypt/package derivatives → deliver

### Protected audio (.kby)

KubanFy storage objects containing playable audio use the `.kby` protected container. KBY v1 uses AES-256-GCM with a per-content key derived from the server-only KBY_MASTER_KEY and the plaintext SHA-256 content hash. The client never receives a permanent storage URL; after authorization it receives a short-lived signed URL plus the key needed to decrypt that exact asset. iOS verifies the authenticated KBY header and plaintext SHA-256 before handing the recovered codec/container to the native audio player.

Provider bytes are therefore never directly deliverable from cache/permanent storage. Artist masters and generated derivatives are also stored as `.kby`.

```

## Entornos

- `development`
- `test`
- `staging`
- `production`

Secretos nunca se comparten entre entornos ni se committean.

## Estado actual del desarrollo

Ver commits y el orden definido en el Plan Técnico (sección 130).
