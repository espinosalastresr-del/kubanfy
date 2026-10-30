---
description: Ejecuta las validaciones pertinentes del bloque actual y revisa regresiones.
agent: build
---

Valida el cambio actual de KubanFy. Inspecciona primero los manifests y workflows para descubrir comandos reales. Ejecuta tests, lint, typecheck y build pertinentes; no inventes comandos ni desactives tests. Revisa git diff y reporta cada resultado PASS/FAIL/NOT RUN, con motivo y archivos afectados. No despliegues.
