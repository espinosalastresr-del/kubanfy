# Production hardening (plan §42)

Checklist mínimo antes de tráfico real de usuarios.

## 1. Secretos y config

- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`
- [ ] `JWT_SECRET` aleatorio ≥ 32 caracteres (no el valor de ejemplo)
- [ ] `SUPER_ADMIN_PASSWORD` fuerte y rotado
- [ ] `DATABASE_URL` / `REDIS_URL` solo en secret manager o env del host
- [ ] `STORAGE_BACKEND=r2` + credenciales R2 (no local disk en prod)
- [ ] CORS limitado a dominios conocidos (no `*`)

La app ya valida en `Settings.production_guards()` que DEBUG esté off y el JWT no sea el de desarrollo.

## 2. TLS y red

- [ ] Terminar TLS en reverse proxy (Caddy / Nginx / Cloudflare)
- [ ] HSTS en el proxy (el middleware ya envía HSTS si `https`)
- [ ] No exponer Postgres/Redis a Internet

## 3. Backups

```bash
export DATABASE_URL='postgresql://...'
export OUT_DIR=/var/backups/kubanfy
./infrastructure/scripts/backup_postgres.sh
```

Programar diario (cron) y probar restore en staging al menos una vez.

## 4. Observabilidad

- [ ] Scraping de `GET /metrics` (Prometheus)
- [ ] Alertas: `kubanfy_db_up`, `kubanfy_redis_up`, tasa 5xx, latencia p95
- [ ] Logs JSON estructurados (`LOG_FORMAT=json`)

## 5. Workers

- [ ] Al menos 1 proceso `python -m app.workers.runner` siempre activo
- [ ] Reinicio automático (systemd / compose `restart: unless-stopped`)

## 6. Load test pre-cutover

```bash
k6 run -e BASE_URL=https://api.tu-dominio loadtests/k6_smoke.js
```

## 7. Runbook rápido

| Síntoma | Acción |
|---------|--------|
| `/health/ready` 503 | Revisar Postgres y Redis |
| Jobs atascados | Logs del worker; tabla `jobs` |
| Disco lleno (local storage) | Migrar a R2; limpiar cache expirado |
| 401 masivos | Rotación JWT / reloj NTP |

## Fuera de alcance hasta el final del plan

- Google Play Billing (§43) — aislado a propósito
