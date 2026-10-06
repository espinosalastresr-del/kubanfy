# KubanFy Cloudflare migration

Target architecture:

- apps/web: React PWA deployed as Cloudflare Workers Static Assets.
- infra/cloudflare/api: FastAPI deployed in Cloudflare Containers.
- R2: encrypted .kby / .kby2 audio assets.
- PostgreSQL: external managed PostgreSQL reached from the Container, with Hyperdrive planned for the final database cutover.
- Redis: external Redis-compatible service until the current Redis usage is migrated to a Cloudflare-native equivalent.
- GitHub -> Workers Builds for deployment.

## Current state

Render remains the rollback environment until the Cloudflare stack passes the complete smoke/regression suite.

R2 provisioning is currently blocked at the Cloudflare account API level. The account API is returning error 10042 ("Please enable R2 through the Cloudflare Dashboard") even after the dashboard activation was reported. Buckets and object migration must not be attempted until the API reports R2 as enabled.

## Required Cloudflare secrets

Set these on kubanfy-api-staging:

- DATABASE_URL
- DATABASE_URL_SYNC
- REDIS_URL
- JWT_SECRET_KEY
- KBY_MASTER_KEY
- OFFLINE_LICENSE_PRIVATE_KEY
- OFFLINE_LICENSE_PUBLIC_KEY
- SUPER_ADMIN_EMAIL
- SUPER_ADMIN_PASSWORD
- R2_ACCESS_KEY_ID
- R2_SECRET_ACCESS_KEY
- R2_SIGNED_URL_EXPIRY_SECONDS

The R2 endpoint and bucket names are non-secret configuration.

## Deployment

### Web

Root directory: apps/web

Build command:

pnpm install --no-frozen-lockfile && pnpm build

Deploy command:

pnpm wrangler deploy

### API

Root directory: infra/cloudflare/api

Build command:

pnpm install --no-frozen-lockfile

Deploy command:

pnpm wrangler deploy

Cloudflare Workers Builds should be connected after the first manual deployment so the Worker names and Wrangler configurations are established.

## Database cutover

Do not rewrite the FastAPI SQLAlchemy/PostgreSQL layer to D1.

The final database migration should:

1. provision an external managed PostgreSQL instance;
2. migrate the Render PostgreSQL data with verification;
3. configure Hyperdrive against the new PostgreSQL origin;
4. switch the Container to the new database connection;
5. keep Render available for rollback;
6. decommission Render only after production validation.

## Storage cutover

R2 is the canonical encrypted media store. Storage is not separated by subscription plan.

- permanent artist/master and encoded assets -> permanent bucket;
- temporary encrypted cache artifacts -> cache bucket;
- .kby remains available for legacy clients;
- .kby2 is the streaming format for the new web client;
- plaintext MP4 is never uploaded to R2.
