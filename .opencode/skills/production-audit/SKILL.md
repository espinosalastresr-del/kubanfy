---
name: production-audit
description: Realiza auditoría previa a beta/producción de funcionalidades KubanFy y comprueba evidencias de calidad.
---

# Production readiness audit

Evalúa por funcionalidad:
- Requisitos y comportamiento esperado.
- Tests unitarios, integración y E2E disponibles.
- Autenticación, autorización, privacidad y abuso.
- Manejo de errores, reintentos, idempotencia y concurrencia.
- Rendimiento, consumo de datos, batería y almacenamiento.
- Observabilidad, logs y alertas.
- Migraciones y compatibilidad.
- CI, build, despliegue y rollback.
- Pruebas manuales en dispositivos reales cuando sean necesarias.

Clasifica cada punto PASS / FAIL / NOT VERIFIED. Adjunta evidencia y comandos. No confundas implementación con verificación en staging o producción. Cierra con bloqueantes y siguientes acciones priorizadas.
