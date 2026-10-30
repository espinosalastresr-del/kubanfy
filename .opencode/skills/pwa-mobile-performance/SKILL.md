---
name: pwa-mobile-performance
description: Mejora clientes web/PWA y experiencias móviles con foco en bajo consumo de datos, resiliencia y accesibilidad.
---

# PWA and mobile performance

Primero detecta qué frontend existe en la rama y lee sus manifests, scripts y documentación.

- Prioriza móvil y accesibilidad.
- Reduce JS, CSS, imágenes, fuentes, requests y payloads.
- Usa caché HTTP/service worker solo para recursos apropiados; nunca caches respuestas privadas de forma insegura.
- Maneja offline, reconexión, estados vacíos y errores.
- Evita polling agresivo, renders y solicitudes duplicadas.
- Respeta límites de almacenamiento y cuota del navegador.
- Comprueba responsive layouts y navegadores/dispositivos objetivo.
- Ejecuta lint, typecheck, tests y build definidos en el package manager real.
