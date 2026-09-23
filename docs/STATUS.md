# Estado del plan técnico (§130) — KubanFy

Actualizado con el desarrollo actual del monorepo.

## Leyenda

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado y usable en código |
| 🟡 | Parcial / falta nativo, integración o hardening |
| ⏳ | Pendiente |

---

## Los 43 pasos del §130

| # | Bloque | Estado | Notas |
|---|--------|--------|-------|
| 1 | repository | ✅ | Monorepo `kubanfy/` |
| 2 | toolchain | ✅ | Python 3.12, pyproject, Makefile |
| 3 | Docker/dev environment | ✅ | `infrastructure/docker-compose.yml` |
| 4 | configuration | ✅ | Pydantic Settings |
| 5 | database | ✅ | SQLAlchemy async |
| 6 | migrations | ✅ | Alembic 001–008 |
| 7 | auth | ✅ | JWT, register/login/refresh |
| 8 | RBAC | ✅ | Roles + permissions |
| 9 | storage abstraction | ✅ | Local + R2 adapter |
| 10 | Redis | ✅ | Locks, rate limits (fail-open) |
| 11 | worker system | ✅ | Claim/complete + handlers |
| 12 | provider interfaces | ✅ | ABC + manager |
| 13 | mock provider | ✅ | Dev/test |
| 14 | MusicEngine | ✅ | update/preview/download |
| 15 | audio validation | ✅ | FFprobe |
| 16 | FFmpeg | ✅ | Transcode pipeline |
| 17 | R2 | 🟡 | Adapter listo; credenciales reales en deploy |
| 18 | cache | ✅ | CacheService + TTL |
| 19 | single-flight | ✅ | Redis lock anti-stampede |
| 20 | download/resume | 🟡 | Download sí; resume HTTP parcial pendiente |
| 21 | user library | ✅ | API + móvil |
| 22 | playlists | ✅ | API + móvil |
| 23 | artist system | ✅ | Modelos + membership |
| 24 | rights | ✅ | LicenseRecord |
| 25 | artist upload pipeline | ✅ | API + pantalla móvil |
| 26 | entitlement | ✅ | Scopes + grant/revoke |
| 27 | payments | ✅ | Manual transfer/cash + admin verify |
| 28 | geo | ✅ | IP server-side, default CU |
| 29 | analytics | ✅ | Events + cola offline móvil |
| 30 | rankings | ✅ | Scoring + snapshots |
| 31 | discovery | ✅ | Home / top / local |
| 32 | anti-abuse | ✅ | Rate limits + score |
| 33 | admin | ✅ | Flags, moderation, audit, suspend |
| 34 | artist portal | 🟡 | En app móvil unificada; pulir UX upload nativo |
| 35 | mobile UI | 🟡 | RN CLI TS; falta `android/`/`ios/` generados en repo |
| 36 | offline player | 🟡 | Cola + índice offline; TrackPlayer nativo pendiente |
| 37 | security hardening | 🟡 | Headers, RBAC, anti-abuse; falta auditoría profunda / WAF |
| 38 | observability | ✅ | Request ID, Prometheus, health |
| 39 | CI/CD | ✅ | API CI + mobile APK/IPA en GitHub Actions |
| 40 | staging | ⏳ | Entorno staging dedicado |
| 41 | load tests | ⏳ | k6/locust u otro |
| 42 | production hardening | ⏳ | Secrets, backups, runbooks |
| 43 | Google Play | ⏳ | **Último** (§135) — solo tras estabilidad |

---

## Resumen numérico

| Categoría | Cantidad |
|-----------|----------|
| ✅ Completos | **32** |
| 🟡 Parciales | **7** (17, 20, 34, 35, 36, 37 + R2) |
| ⏳ Pendientes puros | **4** (40–43) |

**Pasos con trabajo restante: ~11** (7 parciales + 4 pendientes).

Si se cuentan solo hitos “grandes” aún abiertos:

1. Cerrar offline nativo (FS + TrackPlayer + resume)  
2. Generar/commitear `android/` + `ios/` (o confiar solo en scaffold CI)  
3. Staging environment  
4. Load tests  
5. Production hardening (backups, secretos, runbooks)  
6. Google Play (billing adapter — al final)

---

## Commits backend / móvil (referencia)

Ver `git log --oneline` — de bootstrap API hasta mobile CI y upload artista.
