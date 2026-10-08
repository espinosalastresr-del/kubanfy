# Neon PostgreSQL cutover

## Target architecture

```
Cloudflare Worker
    |
    v
Cloudflare Container
    |
    | DATABASE_URL (Neon pooled endpoint)
    v
Neon PostgreSQL / PgBouncer
```

R2 remains the audio/object-storage layer.

Cloudflare Hyperdrive is intentionally not used by the FastAPI Container. Hyperdrive is a Worker-side database accelerator; the Container connects directly to Neon.

## Environment variables

Runtime:

- `DATABASE_URL`: Neon pooled connection string (the hostname contains `-pooler`).
- `DATABASE_URL_SYNC`: optional direct Neon connection string for Alembic migrations.
- `DB_POOL_SIZE`: start small (5).
- `DB_MAX_OVERFLOW`: start small (5).
- `DB_POOL_TIMEOUT`: 30.
- `DB_POOL_RECYCLE_SECONDS`: 300.

Do not commit either database URL.

## Migration from Render

1. Create the Neon project and PostgreSQL database.
2. Obtain both the pooled and direct connection strings.
3. Create a logical backup from the current Render PostgreSQL database:

```bash
pg_dump --format=custom --no-owner --no-acl "$RENDER_DATABASE_URL" > kubanfy-render.dump
```

4. Restore into Neon:

```bash
pg_restore --clean --if-exists --no-owner --no-acl --dbname="$NEON_DIRECT_DATABASE_URL" kubanfy-render.dump
```

5. Verify the schema and row counts.
6. Run the application against the Neon pooled URL.
7. Run Alembic with `DATABASE_URL_SYNC` pointing at the direct URL.
8. Keep Render available as rollback until the Neon deployment has been validated.

## Important PostgreSQL compatibility

KubanFy depends on PostgreSQL transaction semantics including row locks (`FOR UPDATE`), `SKIP LOCKED`, asyncpg, Alembic and transactional idempotency. This is why we are migrating PostgreSQL-to-PostgreSQL rather than moving to D1/SQLite.

## Neon operational notes

Neon's Free plan currently provides 1 GB of PostgreSQL storage per project. Free compute can scale to zero, so the first request after inactivity may incur a cold-start delay. For KubanFy this is acceptable for staging/early launch, but production traffic should be monitored before relying indefinitely on the free tier.

## Verification

After cutover, verify at minimum:

```sql
SELECT version();
SELECT current_database();
SELECT current_user;
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM tracks;
SELECT COUNT(*) FROM jobs;
```

Then exercise authentication, playback/heartbeat, library writes, entitlements and job claiming. These paths use transactional PostgreSQL locking and are the highest-priority migration checks.
