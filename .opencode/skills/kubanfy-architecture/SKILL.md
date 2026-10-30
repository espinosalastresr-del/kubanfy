---
name: kubanfy-architecture
description: Consulta y aplica la arquitectura, límites de módulos y principios de diseño de KubanFy antes de cambios transversales.
---

# KubanFy architecture workflow

1. Lee AGENTS.md y docs/ARCHITECTURE.md, además de los documentos del subsistema.
2. Confirma el estado real del código en la rama actual.
3. Mapea los flujos afectados entre clientes, API, servicios, datos, workers y proveedores.
4. Prefiere el monolito modular y evita microservicios sin necesidad demostrable.
5. Mantén proveedores desacoplados y PostgreSQL como fuente de verdad cuando corresponda.
6. Separa caché, descargas offline y almacenamiento permanente.
7. Documenta decisiones, alternativas, compatibilidad, fallos y pruebas.
8. No inventes módulos ni conviertas diagramas conceptuales en hechos implementados.
