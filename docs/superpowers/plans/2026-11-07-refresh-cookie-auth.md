# Refresh Cookie Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move KubanFy Web to same-origin API requests with an HttpOnly refresh cookie while preserving the existing Bearer contract for legacy/mobile clients.

**Architecture:** The web Worker serves the SPA and proxies only `/api/*` to one fixed HTTPS API origin. FastAPI issues a host-only refresh cookie only for requests whose exact Origin is allowlisted; access tokens remain in browser memory. The React client restores sessions through cookie refresh, coordinates concurrent refreshes, and does not destroy local state on transient network/server errors.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy async sessions, React 19, TypeScript 5.9, Vite 8, Cloudflare Workers/Wrangler 4, pytest, Vitest (only if needed for Worker/client tests).

**Spec:** `docs/superpowers/specs/2026-11-07-refresh-cookie-auth-design.md`

## Global Constraints

- Keep `get_current_user` and protected business routes Bearer-only; do not introduce access-token cookies.
- Refresh cookie attributes: `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth`; omit `Domain`; Max-Age equals configured refresh-token lifetime.
- Accept web cookie auth only for an exact Origin present in `Settings.cors_origins_list`; do not trust a client-supplied flow marker.
- Keep legacy/mobile login and JSON refresh contracts unchanged when the request is not the approved web flow.
- Cookie refresh/logout must reject missing or disallowed Origin and must not mutate a session on rejection.
- Worker upstream is fixed by non-secret `API_ORIGIN`; reject invalid origins and never accept a caller-provided upstream, host, or arbitrary proxy path.
- Proxy only `/api/*`, strip exactly the `/api` prefix, preserve query/method/body streaming/status/relevant headers, and remove hop-by-hop plus reserved internal headers.
- Never log Cookie, Authorization, refresh tokens, or authentication request/response bodies.
- Remove only legacy `sessionStorage.kubanfy.refresh`; preserve `kubanfy.device`, `localStorage` device identity, and `kubanfy_device` cookie.
- Network errors and 5xx responses must not be treated as definitive logout; only definitive authentication rejection clears the in-memory access token/session UI.
- No secrets, remote variables, DNS, deployment, database/session-policy, visual redesign, or background-audio changes.

## Review Focus

- Origin spoofing, missing Origin, null Origin, and lookalike origins: cookie endpoints reject them before refresh/logout state changes.
- Cookie path and deletion attributes: browser receives a host-only cookie scoped only to `/api/v1/auth`, and logout expires the same cookie.
- Simultaneous 401s: only one refresh request is in flight; all waiting requests reuse its result.
- Offline/timeout/5xx during boot or refresh: user is not silently logged out and device identity is retained.
- Proxy path/header abuse and large bodies: no open-proxy behavior, no hop-by-hop leakage, and request/response streams are not buffered.

---

### Task 1: Backend web/legacy auth contract and cookie lifecycle

**Files:**
- Modify: `apps/api/app/api/v1/auth.py`
- Modify: `apps/api/app/schemas/auth.py`
- Modify: `apps/api/app/core/config.py` only if a small cookie/origin helper is needed; reuse `cors_origins_list`.
- Test: `apps/api/tests/test_auth_cookie.py`

**Interfaces:**
- Add a web login response schema containing `user` and an access-token-only token object (`access_token`, `token_type`, `expires_in`).
- Add a helper in the auth router to validate exact Origin against `get_settings().cors_origins_list`.
- Keep `AuthService.login()` and `AuthService.refresh()` as the shared token/session primitives.

- [ ] **Step 1: Write failing API tests** for web login cookie attributes/no refresh token JSON; legacy login retaining refresh token JSON; cookie refresh rotating the cookie; missing/disallowed Origin rejected without mutation; logout revoking only the cookie's session; and Bearer `/me` remaining functional.
- [ ] **Step 2: Run the focused tests and confirm they fail**: `cd apps/api && pytest tests/test_auth_cookie.py -q`.
- [ ] **Step 3: Implement web/legacy response branching in `auth.py`**. Web login is selected only by exact allowlisted Origin. Set the refresh cookie with `httponly=True`, `secure=True` outside explicit localhost development, `samesite="lax"`, `path="/api/v1/auth"`, no domain, and `max_age=refresh_token_expire_days * 86400`. Return only access-token fields in web JSON.
- [ ] **Step 4: Implement cookie-aware `POST /refresh`**. Make the JSON body optional; for an allowlisted web Origin require the refresh cookie and reject ambiguous JSON+cookie credentials; for legacy requests without a web Origin continue to require `RefreshRequest.refresh_token`. Validate Origin before calling `AuthService.refresh()`.
- [ ] **Step 5: Implement `POST /logout`** for the web cookie flow. Validate exact Origin, decode/validate the refresh session, revoke only that session, and expire the cookie using the same Path/Secure/SameSite/HttpOnly attributes. Invalid/missing cookie must not revoke unrelated sessions.
- [ ] **Step 6: Run focused and regression tests**: `cd apps/api && pytest tests/test_auth_cookie.py tests/test_security.py tests/test_password_reset.py -q`. Confirm legacy refresh request schema and Bearer authorization tests still pass.
- [ ] **Step 7: Commit** with message `feat(auth): add same-origin refresh cookie flow`.

### Task 2: Cloudflare web Worker as a constrained same-origin API proxy

**Files:**
- Create: `apps/web/src/worker.ts`
- Modify: `apps/web/wrangler.jsonc`
- Modify: `apps/web/package.json` only for test tooling/scripts if Task 5 establishes it is needed.
- Test: `apps/web/src/worker.test.ts` and Worker test configuration if required by the chosen installed Wrangler-compatible runner.

**Interfaces:**
- Worker environment binding: `API_ORIGIN: string` and the configured static-assets binding.
- Default export: standard Worker `fetch(request, env, ctx)` handler.
- Proxy handler accepts only `/api/` requests and constructs upstream URL from fixed `API_ORIGIN` plus the path after the `/api` prefix.

- [ ] **Step 1: Add failing Worker tests** for fixed-origin forwarding, `/api` prefix stripping, query preservation, method/body streaming, relevant request/response headers, Set-Cookie passthrough, non-API SPA asset fallback, rejection of malformed API_ORIGIN, and rejection of paths outside `/api/` as proxy requests.
- [ ] **Step 2: Confirm the Worker test runner is compatible** with the repository's Wrangler `4.136.0` and Node `>=22.12.0`; prefer existing installed tooling, otherwise add the smallest supported Vitest/Workers pool setup and lockfile changes.
- [ ] **Step 3: Implement `src/worker.ts`**. Validate API_ORIGIN as HTTPS origin-only (no credentials, path, query, or fragment); build the upstream URL without accepting caller-controlled destinations; preserve request streaming and response streaming; remove hop-by-hop and reserved internal headers; do not log sensitive headers or bodies.
- [ ] **Step 4: Configure `wrangler.jsonc`** with `main`, the static-assets binding, and non-secret `API_ORIGIN` example for staging: `https://kubanfy-api-staging.globumlatinmusic.workers.dev`. Keep existing SPA asset handling and observability. Do not set remote variables or deploy.
- [ ] **Step 5: Run Worker tests and local type/config checks** using the exact repository-local package scripts; expected result is all proxy contract tests pass and Wrangler accepts the local configuration.
- [ ] **Step 6: Commit** with message `feat(web): proxy api through same-origin worker`.

### Task 3: React client refresh lifecycle and removal of JavaScript refresh-token storage

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/App.tsx`
- Test: `apps/web/src/api.test.ts`

**Interfaces:**
- Replace token setter accepting a refresh token with access-token-only state management.
- Add `restoreSession(): Promise<boolean>` to refresh through the cookie and establish a new in-memory access token.
- Add `logout(): Promise<void>` to call the server logout endpoint before clearing local access state; callers still clear UI state after the operation settles.
- Add a module-scoped single-flight refresh promise shared by all requests.

- [ ] **Step 1: Write failing client tests** for legacy refresh key removal at module initialization; no refresh token persisted; login uses same-origin relative paths and `credentials: "same-origin"`; boot refresh restores access; concurrent 401s produce one refresh; refresh 401 clears auth; refresh network/5xx preserves auth state; and logout calls the server and clears the access token.
- [ ] **Step 2: Run the focused client tests and confirm they fail** with the current token-storage implementation.
- [ ] **Step 3: Refactor `api.ts`** to remove `API`, `VITE_API_BASE_URL`, `refreshToken`, and all refresh-token reads/writes. Route API requests through `/api/v1/...`; include same-origin credentials; store only access token in module memory.
- [ ] **Step 4: Implement `restoreSession()` and single-flight refresh**. Cookie refresh must be attempted during boot; only a definitive 401/403 clears auth. Network errors and 5xx propagate as transient failures without clearing local identity.
- [ ] **Step 5: Update request retry logic** so a 401 waits for the shared refresh operation and retries the original request at most once; do not retry unsafe writes after transport errors.
- [ ] **Step 6: Update `App.tsx` boot/login/logout paths**. Boot calls `restoreSession()` before `me()`; transient restore failure must not be interpreted as a definitive guest/logout; logout invokes the API and then clears UI state. Preserve device ID storage/cookie.
- [ ] **Step 7: Run client tests and `pnpm build`** from `apps/web`; expected result is tests pass, TypeScript check passes, and Vite build succeeds.
- [ ] **Step 8: Commit** with message `feat(web): use httponly refresh cookie`.

### Task 4: CORS/origin configuration and operational documentation

**Files:**
- Modify: `apps/api/app/main.py` only if middleware needs alignment with the shared allowlist.
- Modify: `apps/api/app/core/config.py` only if required to normalize/reuse existing origin configuration.
- Create or modify: `docs/deployment/auth-cookie-proxy.md`

**Interfaces:**
- Backend cookie-flow Origin validation and CORS middleware both consume the same `Settings.cors_origins_list`.
- Deployment documentation describes `API_ORIGIN` as a non-secret Worker variable; no remote change is performed by this task.

- [ ] **Step 1: Add failing config tests** proving exact staging origin is present, lookalike origins are not accepted, and no wildcard-with-credentials behavior is introduced.
- [ ] **Step 2: Implement the smallest config/middleware adjustment** needed to keep the cookie flow and CORS allowlist aligned; do not duplicate the origin list.
- [ ] **Step 3: Document** staging/local API_ORIGIN values, cookie attributes, legacy compatibility, and the fact that deployment must set the Worker variable separately after code review.
- [ ] **Step 4: Run** `cd apps/api && pytest tests/test_auth_cookie.py tests/test_config.py -q`; expected result is exact-origin tests pass.
- [ ] **Step 5: Commit** with message `docs(auth): document same-origin cookie configuration`.

### Task 5: Integrated regression and release-readiness checks

**Files:**
- Modify tests created in Tasks 1–3 as required.
- No production behavior changes unless a failing acceptance test demonstrates a defect.

**Interfaces:**
- Uses the backend, Worker, and client contracts established in Tasks 1–3.

- [ ] **Step 1: Add an integrated contract test** covering web login -> Set-Cookie -> cookie refresh -> rotated Set-Cookie -> `/me` with Bearer -> logout -> cookie expiry; verify the previous refresh token cannot be replayed.
- [ ] **Step 2: Add concurrency regression coverage** proving simultaneous client 401s trigger one refresh and the rotated token is not raced/reused.
- [ ] **Step 3: Run backend suite**: `cd apps/api && pytest -q`; expected result is PASS, or document unrelated pre-existing failures separately with exact output.
- [ ] **Step 4: Run frontend/Worker suite and build** from `apps/web`: test script, `pnpm build`, and Wrangler local config validation; expected result is all checks PASS.
- [ ] **Step 5: Review the final diff** for secrets, token logging, accidental device-ID deletion, wildcard credential CORS, unbounded body buffering, and changes outside approved scope.
- [ ] **Step 6: Record manual Safari/iOS staging validation steps** (login, reload, offline transition, refresh after expiry, logout) without deploying or claiming that browser validation has occurred.
- [ ] **Step 7: Commit** with message `test(auth): cover cookie refresh integration`.

## Execution Notes

- Tasks 1–3 are ordered because the API contract is consumed by the Worker and the Worker is consumed by the client. Task 4 can be performed alongside Task 1 once the shared allowlist behavior is clear; Task 5 follows all implementation tasks.
- Keep each task's test-first cycle small. Do not batch unrelated refactors or change the session/device policy.
- Do not deploy, modify Cloudflare/Render remote variables, alter DNS, rotate secrets, or merge the branch as part of this plan.
- Safari/iOS validation remains a required pre-release manual check because automated Worker/client tests cannot reproduce every WebKit cookie lifecycle behavior.
