# Progreso vs Plan Técnico §130

Orden oficial de desarrollo (43 pasos). Actualizado tras production hardening base.

| # | Paso | Estado |
|---|------|--------|
| 1 | repository | ✅ |
| 2 | toolchain | ✅ |
| 3 | Docker/dev environment | ✅ |
| 4 | configuration | ✅ |
| 5 | database | ✅ |
| 6 | migrations | ✅ (001–008) |
| 7 | auth | ✅ |
| 8 | RBAC | ✅ |
| 9 | storage abstraction | ✅ |
| 10 | Redis | ✅ |
| 11 | worker system | ✅ |
| 12 | provider interfaces | ✅ |
| 13 | mock provider | ✅ |
| 14 | MusicEngine | ✅ |
| 15 | audio validation | ✅ |
| 16 | FFmpeg | ✅ |
| 17 | R2 | 🟡 adapter; faltan credenciales prod |
| 18 | cache | ✅ |
| 19 | single-flight | ✅ |
| 20 | download/resume | 🟡 download OK; resume HTTP por rangos incompleto |
| 21 | user library | ✅ |
| 22 | playlists | ✅ |
| 23 | artist system | ✅ |
| 24 | rights | ✅ |
| 25 | artist upload pipeline | ✅ |
| 26 | entitlement | ✅ skeleton |
| 27 | payments | ✅ manual |
| 28 | geo | ✅ |
| 29 | analytics | ✅ |
| 30 | rankings | ✅ |
| 31 | discovery | ✅ |
| 32 | anti-abuse | ✅ |
| 33 | admin | ✅ |
| 34 | artist portal | ✅ |
| 35 | mobile UI | ✅ |
| 36 | offline player | 🟡 engine RNTP/RNFS; falta link nativo device |
| 37 | security hardening | 🟡 headers, guards prod, RBAC; falta review/pentest |
| 38 | observability | ✅ |
| 39 | CI/CD | ✅ |
| 40 | staging | 🟡 compose+migrate; falta host dedicado |
| 41 | load tests | 🟡 k6 smoke + auth smoke |
| 42 | production hardening | 🟡 checklist, backups script, runbook |
| 43 | Google Play | ❌ aislado al final |

## Conteo

- **Completos (✅):** 33
- **Parciales (🟡):** 9 — 17, 20, 36, 37, 40, 41, 42 (+ detalles)
- **Pendientes fuertes (❌):** 1 — Google Play (§43)

Para **dar por cerrado el MVP técnico** sin Google Play: cerrar los 🟡 críticos (R2 prod, resume, offline nativo en device, staging host, load auth/download, review seguridad).

**Pasos restantes hasta finalizar el plan completo (incl. Google Play): ~10 unidades de trabajo** (9 parciales + 1 Google Play).
