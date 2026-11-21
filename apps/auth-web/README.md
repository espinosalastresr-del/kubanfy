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
