# Auditoría de alineación con el Plan Técnico — 2026-09-24

## Alcance

Auditoría del branch `feat/release-track-management` contra las decisiones vigentes del Plan Técnico de KubanFy y las decisiones posteriores confirmadas durante el desarrollo.

Regla de validación: una prueba funcional solo es válida si atraviesa el flujo real establecido; no se aceptan atajos que sustituyan ProviderManager, autorización, KBY, storage o reproducción.

## Hallazgos corregidos

### 1. Cliente móvil documentado de forma incorrecta
La documentación todavía describía React Native. La decisión vigente es:
- Android nativo: Kotlin + Media3/ExoPlayer.
- iOS nativo: Swift/SwiftUI + AVFoundation.
- CI separado por plataforma.

README y ARCHITECTURE fueron corregidos.

### 2. Mock provider habilitado por defecto
El registry podía incluir `MockProvider` por defecto y el API lo utilizaba en runtime. Esto permitía que el camino de desarrollo se pareciera demasiado al de producción.

Corrección:
- `create_default_registry()` no incluye mock por defecto.
- MusicEngine solo incluye mock en entorno de tests.
- El API runtime usa registry sin mock.

El fixture de staging no sustituye al flujo de producción.

### 3. Existía un camino legacy que almacenaba audio sin KBY
`MusicEngine._store_and_cache()` almacenaba bytes de audio directamente en R2.

Corrección:
- El helper ahora delega siempre a `CacheService.store_bytes()`.
- La entrada pasa por validación → KBY → R2.
- El lookup de cache exige objetos `.kby`.

### 4. Endpoint raw de contenido incompatible con KBY
`GET /music/content/{track_id}` podía servir directamente bytes del objeto almacenado mediante Range. Para un objeto KBY eso equivale a exponer el contenedor protegido como si fuera audio reproducible.

Corrección:
- El endpoint queda deshabilitado con HTTP 410.
- El streaming KBY por rangos se implementará posteriormente como un mecanismo consciente de KBY, no como Range sobre ciphertext entregado al reproductor.

### 5. Se endureció KBY en producción
`KBY_MASTER_KEY` no puede permanecer con el valor dev-only/change-me en producción.

## Componentes alineados

- FastAPI + PostgreSQL + Redis + workers + FFmpeg + R2.
- MusicEngine separado de proveedores.
- ProviderManager/Registry.
- Cache antes de adquisición externa.
- Single-flight.
- Audio validation/provenance.
- AudioQuality LOW/MEDIUM/LOSSLESS.
- R2 cache temporal y R2 permanent para catálogo first-party.
- Masters y derivados first-party en `.kby`.
- Entitlements separados de pagos.
- Device/session management.
- Offline licenses firmadas y vinculadas a dispositivo.
- Métricas de engagement calificadas por servidor.
- Tendencias no dependen de eventos de engagement autoritativos enviados directamente por el cliente.
- Rights/royalty skeleton.
- PaymentOrder/entitlement idempotency skeleton.
- Google Play desactivado y pospuesto.

## Gaps que siguen abiertos y no deben marcarse como terminados

1. Playback E2E real completo:
   Track → AudioAsset → autorización → KBY/R2 → signed URL → cliente → verificación/descifrado → player → heartbeat/renovación/recuperación.

2. Integración completa de seguridad de playback con device/session binding y controles anti-abuso.

3. KBY streaming/range-aware para bajo consumo. La implementación actual de iOS descarga el KBY completo y lo descifra antes de AVPlayer; es funcional para validar el circuito, pero no es todavía la optimización final para conectividad cubana.

4. Offline persistente completo: cache local y descarga offline deben permanecer separados, con licencia, expiración, revocación, integridad y recuperación.

5. Analytics/rankings de producción: las métricas autoritativas deben generarse a partir de workflows de servidor y alimentar rankings mediante workers.

6. Provider integrations reales y política completa de fallback/health/circuit breaker deben probarse con proveedores reales antes de considerar adquisición externa cerrada.

7. Rights/licensing y royalties permanecen como esqueleto funcional; no deben convertirse todavía en un desvío del desarrollo del core de reproducción.

8. Pagos manuales permanecen como skeleton; Google Play/Billing sigue fuera del camino crítico hasta que la aplicación funcional y las auditorías estén cerradas.

## Orden de trabajo después de esta auditoría

1. CI verde sobre todos los cambios de alineación.
2. Verificación del fixture staging como KBY.
3. Prueba E2E real del playback.
4. Cierre de antipiratería integrada.
5. Streaming KBY eficiente para baja conectividad.
6. Offline persistente.
7. Analytics/rankings de producción.
8. Rights/licensing.
9. Payments.
10. Google Play/Billing al final.

No se debe adelantar UI secundaria, monetización o integraciones comerciales por delante de los elementos del core indicados arriba.
