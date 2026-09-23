# Security baseline (plan §37 / §109)

## Already in code

- JWT access + refresh; bcrypt passwords
- RBAC server-side (client UI is not authorization)
- Rate limits (login, register, search, download) via Redis (fail-open if Redis down)
- Security headers middleware (nosniff, frame deny, referrer, HSTS on HTTPS)
- Maintenance mode (`FEATURE_MAINTENANCE_MODE=true`)
- Production guards: DEBUG off, JWT not default, admin password not default
- Audit log API for admin actions
- Storage path traversal protection on local backend
- No secrets in git (`.env` gitignored)

## Before production

1. Rotate all secrets; use secret manager
2. TLS at proxy; restrict CORS and `ALLOWED_HOSTS`
3. Enable R2 (no local disk for audio in prod)
4. Run `k6` smoke + auth against staging
5. Review admin permission assignments
6. Backup + restore drill (`infrastructure/scripts/backup_postgres.sh`)

## Incident notes

- Suspend user: admin API
- Revoke sessions: delete devices / rotate JWT secret (logs out everyone)
- Rate limit keys: Redis `rl:*`
