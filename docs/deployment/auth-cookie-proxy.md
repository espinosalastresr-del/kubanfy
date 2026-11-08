# Same-origin API proxy and browser refresh-cookie authentication

## Request flow

The web client sends API traffic to its own origin under `/api/*`. The Cloudflare web Worker forwards only those requests to the fixed HTTPS origin configured by `API_ORIGIN`, removes the `/api` prefix, and preserves the query string. The browser never chooses the upstream host.

The staging value is:

```text
API_ORIGIN=https://kubanfy-api-staging.globumlatinmusic.workers.dev
```

`API_ORIGIN` is a non-secret Worker variable. It must be an HTTPS origin only: no credentials, path, query, fragment, or trailing slash. The checked-in staging value lives in `apps/web/wrangler.jsonc`. No remote Cloudflare variable, DNS record, secret, or deployment is changed by this implementation.

For local Worker development, use the staging API origin or an HTTPS tunnel to a local API. The Worker intentionally rejects plain HTTP upstream origins.

## Browser session contract

- Login from an exact allowlisted browser `Origin` sets the `kubanfy_refresh` cookie.
- The cookie is host-only (no `Domain`), `HttpOnly`, `Secure`, `SameSite=Lax`, and scoped to `Path=/api/v1/auth`.
- `Max-Age` matches the configured refresh-token lifetime.
- Browser JSON responses contain only the access token, token type, and expiry. The access token stays in JavaScript memory.
- On startup, the client calls `POST /api/v1/auth/refresh` through the same-origin proxy. A successful refresh rotates the cookie and returns a new access token.
- Logout calls `POST /api/v1/auth/logout`, revokes only the cookie's session, and expires the cookie with the same scope.
- The client removes the obsolete `sessionStorage.kubanfy.refresh` key. It must preserve `kubanfy.device`, `localStorage` device identity, and the `kubanfy_device` cookie.
- Native/mobile clients without a browser `Origin` retain the legacy JSON refresh-token contract. Protected business routes remain Bearer-token authenticated.

A transient network error or 5xx during refresh is not a definitive logout. Only a 401/403 refresh rejection clears the in-memory access token.

## Origin and CORS configuration

The browser cookie endpoints require an exact `Origin` match against `Settings.cors_origins_list`. Missing, `null`, lookalike, and unlisted origins are rejected before login/session state changes, refresh rotation, or logout revocation.

FastAPI's CORS middleware uses the same `cors_origins_list` property. Do not maintain a second allowlist. In staging, the canonical web Worker origin `https://kubanfy-web-staging.globumlatinmusic.workers.dev` is added by the settings property. Other origins are configured through the comma-separated `CORS_ORIGINS` setting.

Credentialed CORS must use explicit origins. A wildcard (`*`) is rejected.

## Deployment checklist

Before deploying the web Worker and API together:

1. Confirm the deployed web Worker has the intended `API_ORIGIN`.
2. Confirm the API's `CORS_ORIGINS` includes the exact public web origin (staging's canonical Worker origin is added automatically).
3. Confirm the API and web Worker are served over HTTPS.
4. Validate login, cookie attributes, reload/refresh rotation, Bearer `/me`, and logout cookie expiry.
5. Verify a legacy/mobile login and JSON refresh still return the legacy token contract.
6. Exercise offline and 5xx refresh failures; they must not silently revoke local identity.
7. Repeat the cookie lifecycle on Safari/iOS. Automated tests do not replace this WebKit check.

No staging deployment or remote configuration change has been performed as part of this work.
