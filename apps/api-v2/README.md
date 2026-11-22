# KubanFy 2 — Authentication API

This service is isolated from the previous implementation at apps/api. It owns its dependencies, migration history, tests, Docker image, and Cloudflare Container Worker.

## Scope
- Registration with full name, age, email, password, password confirmation, country of origin, and explicit acceptance of the configured terms version.
- Email/password login.
- Persistent, revocable server-side sessions using an opaque HttpOnly cookie.
- Current-session inspection and logout.
- Country/IP context refresh from trusted Cloudflare headers on authenticated requests.
- Liveness and database-readiness endpoints.

Music product endpoints and subscription enforcement are still being built. Authentication now includes database-backed RBAC for Free, Premium, Artist, and Admin.

## Database isolation
All tables live in PostgreSQL schema auth_v2. The isolated Neon branch is kubanfy-definitive-auth; production remains untouched. Alembic uses a direct Neon URL. The running API uses the pooled Neon URL to avoid holding unnecessary direct connections.

## Local development
1. Copy .env.example to .env and configure PostgreSQL.
2. Install with python -m pip install -e ".[dev]".
3. Run alembic upgrade head.
4. Start with uvicorn app.main:app --reload --port 8000.
5. Test with pytest -q.

## Authorization (RBAC)\n\n- Alembic revision `0003_roles_permissions` creates roles, permissions, assignments, and role-permission mappings in `auth_v2`.\n- Seeds `free`, `premium`, `artist`, and `admin`; existing and newly registered accounts receive `free` unless explicitly granted another role.\n- Login and `/api/v1/auth/me` return the server-resolved `user.roles` and `user.permissions`. The browser cannot grant or change either value.\n- Protect feature endpoints with `require_roles(...)` or `require_permissions(...)` from `app.api.authorization`; the sample `GET /api/v1/admin/access` requires `admin.dashboard.access`.\n- A first admin can be provisioned explicitly with `scripts/bootstrap_admin.py`. Set the `KUBANFY_BOOTSTRAP_ADMIN_*` variables in the deployment/local environment and the one-time `KUBANFY_BOOTSTRAP_ADMIN_ENABLED=1` switch. It never stores or prints the password, and an existing account's password is not overwritten.\n\n## API\n- POST /api/v1/auth/register
- POST /api/v1/auth/login
- POST /api/v1/auth/logout
- GET /api/v1/auth/me\n- GET /api/v1/admin/access (admin permission required)
- GET /health/live
- GET /health/ready

OpenAPI docs are disabled in production.

## Licence notice
The legal licence is not defined yet. Registration records explicit consent to the configured placeholder version draft-pending-v1. This is not final legal text; production registration must remain disabled until the actual agreement is approved and presented.

## Required GitHub Actions secrets for deployment
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ACCOUNT_ID
- NEON_DATABASE_URL — direct URL for Alembic migrations on the isolated Neon branch, never production.
- NEON_DATABASE_URL_POOLED — pooled URL for the runtime API, on the same isolated branch.
- Optional CORS_ORIGINS — comma-separated frontend origins.

The deployment job skips Cloudflare until required secrets exist. Never commit .env or credentials.

## Password recovery (provider remains disabled by default)
- `POST /api/v1/auth/password/forgot` always returns a generic 202 response to reduce account enumeration.
- `POST /api/v1/auth/password/reset` accepts a single-use token and a new password; tokens are stored only as SHA-256 hashes, expire after the configured interval, and password changes invalidate all sessions.
- Migration `0002_password_reset` creates isolated token storage in `auth_v2`.
- Transactional email settings (`EMAIL_PROVIDER_API_KEY`, `EMAIL_FROM`, `AUTH_WEB_URL`) are intentionally blank. No recovery mail is sent until a provider is selected and configured. The current optional adapter uses Resend only when credentials and sender/origin are supplied; the provider decision remains pending.
