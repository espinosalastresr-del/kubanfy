---
name: database-migrations
description: Diseña y revisa migraciones Alembic y cambios de esquema PostgreSQL sin pérdida de datos.
---

# Database migration workflow

- Inspecciona modelos, migraciones anteriores, constraints, índices y consultas consumidoras.
- Determina impacto en tablas grandes, locks, defaults, nullability y datos existentes.
- Prefiere migraciones expand/contract compatibles con versiones desplegadas.
- Evita DROP/rename destructivos en un solo paso cuando pueda afectar despliegues activos.
- Define upgrade y downgrade razonables; explica si downgrade no es seguro.
- Añade tests y valida autogenerate/diff cuando el proyecto lo soporte.
- No ejecutes migraciones en producción sin aprobación explícita y plan de backup/rollback.
