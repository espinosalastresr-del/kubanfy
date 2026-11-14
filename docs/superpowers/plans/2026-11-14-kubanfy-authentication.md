# KubanFy 2 Authentication Implementation Plan

> Executed natively in the isolated KubanFy-definitive branch.

**Goal:** Deliver a focused FastAPI registration/login/session service backed by an isolated Neon branch and deployed through Cloudflare Containers.

**Architecture:** A new apps/api-v2 package keeps all code and migrations separate from the previous apps/api. PostgreSQL objects live in schema auth_v2; authentication uses Argon2id password hashes and opaque, hashed, server-side session tokens in HttpOnly cookies. A small Cloudflare Worker forwards traffic to the FastAPI Container.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL/Neon, Argon2id, Cloudflare Containers, Wrangler, GitHub Actions, pytest.

## Constraints
- Never modify the existing apps/api implementation or Neon production branch.
- Never commit credentials, connection strings, passwords, or environment files.
- Keep music, subscriptions, devices, account recovery, artist/admin, and other product modules out of this phase.
- Record explicit acceptance of a versioned terms placeholder; final legal text remains pending and must be approved before production use.
- Runtime database connections use the async URL; Alembic uses a direct synchronous URL.

## Review focus
- Duplicate/case-variant email registration must not create duplicate accounts.
- Password confirmation and terms consent must be validated server-side.
- Passwords and raw session tokens must never be persisted.
- Expired, revoked, or inactive-user sessions must not authenticate.
- Cookie flags and origin checks must protect browser sessions.
- Untrusted client-supplied geolocation headers must not be accepted outside the trusted Cloudflare edge.
