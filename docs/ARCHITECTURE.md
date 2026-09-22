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

Una sola app React Native CLI + TypeScript atiende:

- **Listener** — todos los usuarios autenticados
- **Artist** — roles ARTIST / ARTIST_MANAGER
- **Admin** — roles de operación (SUPER_ADMIN, ADMIN, MODERATOR, …)

El conmutador de modo es solo UI. **La autorización real es del API** (JWT + RBAC + audit).
No se confía en el cliente para roles, país ni entitlements.

Builds de release: GitHub Actions → APK (Android) e IPA (iOS).

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
               HIT  → R2 signed URL
               MISS → ProviderManager → acquire → validate
                     → store master → transcode → deliver
```

## Entornos

- `development`
- `test`
- `staging`
- `production`

Secretos nunca se comparten entre entornos ni se committean.

## Estado actual del desarrollo

Ver commits y el orden definido en el Plan Técnico (sección 130).
