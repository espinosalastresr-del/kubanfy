# KubanFy — Backend completion audit

This document is the implementation checkpoint before final mobile work.

## Backend boundary

The backend is considered code-complete when the following are implemented and covered by CI:

- Auth, RBAC, admin permissions and audit
- PostgreSQL/Alembic persistence
- Local/R2 storage abstraction
- Redis locks, rate limits and single-flight
- Provider abstraction and MusicEngine
- Audio validation/transcoding
- Cache + HTTP Range/resume
- First-party Artist → Release → Track → AudioAsset → LicenseRecord ownership
- Public artist catalog
- Release/track lifecycle management
- Entitlements and manual payments with idempotent fulfillment
- Geo, analytics, rankings and discovery
- Anti-abuse, maintenance mode and security headers
- Worker processing
- Staging bootstrap, load smoke and backup/runbook tooling

## Important ownership invariant

External provider results remain ProviderTrack/cache objects. They do not automatically become owned Track records.

Owned/offline content follows:

Artist → Release → Track → AudioAsset → LicenseRecord → permanent storage → entitlement/download.

## Current hardening in this branch

- Release/track mutations require artist membership and appropriate role.
- Deleted releases/tracks cannot be edited or silently resurrected.
- Publishing requires validated audio and active streaming rights.
- Release publication requires all contained tracks to be published.
- Payment approval is serialized with a database row lock.
- Payment entitlement fulfillment is idempotent by payment_order_id.
- Entitlement expiration is evaluated at the exact expiration instant.
- Ranking signals are bounded and unpublished tracks are excluded from ranked output.
- HTTP Range resume and download anti-abuse remain enforced by the existing MusicEngine/API path.

## Intentionally external / deployment-time work

- Real R2 credentials and production secret manager configuration.
- Real staging host/infrastructure.
- TLS/reverse proxy and WAF/pentest.
- Google Play Billing, which remains the final monetization integration.

Those are deployment/integration tasks, not missing backend domain implementation.
