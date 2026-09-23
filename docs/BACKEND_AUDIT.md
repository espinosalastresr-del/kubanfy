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
- Safe versioned audio replacement with atomic active-generation switch
- Collaborator split generations and append-only royalty ledger
- Device-bound offline licenses with short-lived signed authorization, validation, and device revocation
- Server-side publication scheduling via durable jobs
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
- Offline authorization is bound to the authenticated device claim, asset version and content hash; device revocation invalidates its offline licenses.
- Release publication scheduling is server-side and superseded schedules are ignored.
- Royalty split updates lock the owned scope row; ledger/account/settlement idempotency uses nested transactions so concurrent retries do not roll back unrelated work.
- Royalty settlements now have an explicit pending → approved → paid/rejected lifecycle; payout marking appends an idempotent debit ledger entry and is bound to the target artist.
- Audio assets enforce one generation/quality/source tuple at the database level, preventing duplicate derivative rows under concurrent workers.
- HTTP Range resume and download anti-abuse remain enforced by the existing MusicEngine/API path.

## Remaining mobile security work before backend/mobile gate

The backend now issues and validates device-bound offline licenses, but the mobile client still needs the final secure-storage/encrypted-container integration. Raw audio files must not be treated as the completed anti-piracy boundary until that layer is implemented and tested.

## Intentionally external / deployment-time work

- Real R2 credentials and production secret manager configuration.
- Real staging host/infrastructure.
- TLS/reverse proxy and WAF/pentest.
- Google Play Billing, which remains the final monetization integration.
- CI lint is now blocking; Alembic migrations are exercised to head before the API image build.

Those are deployment/integration tasks, not missing backend domain implementation.
