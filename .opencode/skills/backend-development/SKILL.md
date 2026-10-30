---
name: backend-development
description: Procedimiento para desarrollar y probar el backend FastAPI de KubanFy.
---

# Backend development

- Lee AGENTS.md, apps/api/pyproject.toml y la documentación/API del módulo.
- Confirma versiones y estructura real antes de importar patrones.
- Sigue FastAPI, Pydantic v2, SQLAlchemy 2.x y Alembic según el código existente.
- Mantén validación, autorización, ownership y lógica de negocio en servidor.
- Usa transacciones y consultas seguras; evita N+1 y operaciones bloqueantes en rutas async.
- Añade tests unitarios/API para éxito, validación, errores, permisos y límites.
- Ejecuta los comandos definidos por el proyecto; no inventes scripts.
- Para migraciones, revisa upgrade/downgrade y compatibilidad con datos existentes.
- Nunca debilites seguridad para hacer pasar tests.
