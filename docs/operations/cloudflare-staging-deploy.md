# Cloudflare API staging deployment

## Deployment path

The `staging/canonical` branch is the only branch allowed to deploy the API Worker automatically. The deployment job runs only after the existing API tests, API Docker build, and web PWA build have succeeded.

The job runs Wrangler 4.136.0 from `infra/cloudflare/api/wrangler.jsonc`. Because this Worker uses Cloudflare Containers, `wrangler deploy` also builds and publishes the image from `apps/api/Dockerfile` and requests the Container rollout. This is intentionally a full deploy, not `wrangler versions upload`.

A manual workflow dispatch is also supported, but only when the selected ref is `staging/canonical`.

## One-time GitHub credential setup

Create a Cloudflare API token for CI/CD:

1. Open the Cloudflare dashboard for the account that owns `kubanfy-api-staging`.
2. Create an account API token with the **Workers Editor** permission.
3. Scope it to the individual Worker `kubanfy-api-staging` if Cloudflare offers that resource scope for the selected role. Do not grant account-wide Administrator access.
4. Copy the token once; do not commit it or send it in chat.
5. In GitHub, open `espinosalastresr-del/kubanfy` → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
6. Create the secret named exactly `CLOUDFLARE_API_TOKEN` and paste the token value.

The account ID is intentionally fixed in the workflow to the Cloudflare account that currently owns the staging Worker, so a second GitHub secret is not required.

## Safety boundaries

- The workflow is restricted to `staging/canonical` and `kubanfy-api-staging`.
- Pull-request CI never receives the Cloudflare token and never deploys.
- The deploy job waits for all three existing CI jobs.
- The workflow does not create or migrate databases and does not change Neon.
- Existing Worker secrets are not written into the repository. Wrangler deployments preserve existing encrypted Worker secrets.
- Keep the Wrangler configuration synchronized with dashboard-managed plain-text variables; Wrangler treats configured variables as the deployment source of truth.

## First deployment validation

After the workflow is merged and the GitHub secret exists:

1. Confirm the deploy job finishes successfully.
2. Confirm a new deployment/version appears for `kubanfy-api-staging`.
3. Check `GET https://kubanfy-api-staging.globumlatinmusic.workers.dev/health/ready`.
4. Inspect the API Container logs if readiness is not healthy.
5. Exercise a real transactional email through KubanFy's API only after the API readiness checks pass.

A successful Wrangler deployment proves upload and rollout initiation; it does not by itself prove application readiness or end-to-end email delivery.
