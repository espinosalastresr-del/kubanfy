# KubanFy Auth Web

Standalone React + TypeScript authentication UI, isolated from the legacy frontend.

## Run locally

```bash
npm install
cp .env.example .env
npm run dev
```

## Build

```bash
npm run build
```

Configure `VITE_AUTH_API_URL` to the Auth v2 Worker origin. Requests use `credentials: include` for the HttpOnly session cookie.

Implemented UI flows: login, registration, forgot password, and token-based password reset. Login and registration use the deployed Auth v2 endpoints. The password recovery endpoints (`POST /api/v1/auth/password/forgot` and `POST /api/v1/auth/password/reset`) must be added to the API before those two screens can complete server-side.

The terms/license links are placeholders until the approved legal text and canonical routes are published. Registration currently reflects the API's provisional terms version; do not enable public registration until legal approval.

## Cloudflare deployment
The `wrangler.jsonc` deploys the Vite SPA as Workers Static Assets with SPA fallback. The Auth Web workflow builds on PRs and deploys automatically on pushes to `KubanFy-definitive` when `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` are present. It uses a separate Worker named `kubanfy-auth-web`; confirm its generated `workers.dev` URL and add that origin to the API's `CORS_ORIGINS` before browser login is expected to work.

Password recovery screens now call the API endpoints. The email delivery provider remains unconfigured, so forgot-password intentionally returns a generic accepted response but cannot deliver a message until provider selection/configuration.
