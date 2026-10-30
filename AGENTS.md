# KubanFy — instrucciones para agentes

## Misión y contexto
KubanFy es una plataforma de música orientada al mercado cubano. Prioridades: desarrollo eficiente, seguridad, fiabilidad, experiencia móvil y funcionamiento con conexiones lentas, caras e inestables.

La arquitectura documentada combina FastAPI/Python 3.12+, Pydantic v2, SQLAlchemy/Alembic, PostgreSQL, Redis, Cloudflare R2, workers y clientes móviles/web. La implementación real puede evolucionar: verifica siempre el repositorio y su documentación antes de asumir que un módulo existe.

## Reglas de trabajo
- Inspecciona el código, el estado de Git, los tests y los documentos relevantes antes de proponer cambios.
- No inventes rutas, comandos, dependencias, endpoints, variables ni capacidades.
- Reutiliza patrones existentes. Evita reescrituras y dependencias nuevas sin justificación.
- Trabaja en bloques pequeños y coherentes; no mezcles funcionalidades no relacionadas.
- Antes de implementar, resume objetivo, archivos afectados, riesgos, pruebas y migraciones.
- No continúes a otro bloque si el bloque actual deja validaciones fallidas sin explicar.
- No ocultes errores, no desactives tests para conseguir un CI verde y no reduzcas controles de seguridad para acelerar.
- Mantén los cambios compatibles con el código y los datos existentes.

## Ciclo obligatorio por bloque
1. Diagnosticar implementación actual y dependencias.
2. Proponer el cambio mínimo suficiente.
3. Implementar y añadir/actualizar tests.
4. Ejecutar las comprobaciones disponibles y pertinentes.
5. Revisar diff, seguridad, rendimiento y regresiones.
6. Informar resultados exactos, comandos ejecutados y limitaciones.

Clasifica cada resultado como IMPLEMENTADO, TESTEADO, DESPLEGADO o VERIFICADO EN PRODUCCIÓN. No uses estas categorías como sinónimos.

## Backend y API
- Respeta FastAPI, Pydantic v2, SQLAlchemy 2.x y convenciones existentes.
- Valida entradas en el servidor y aplica autenticación, autorización y propiedad de recursos en backend.
- No confíes en roles, país, suscripción, permisos ni entitlements enviados por el cliente.
- Mantén contratos API coherentes y errores que no filtren detalles internos.
- Usa transacciones, consultas parametrizadas y migraciones Alembic seguras.
- Considera compatibilidad hacia atrás y datos ya existentes.

## Clientes, PWA y audio
- Prioriza móvil, accesibilidad, carga progresiva y bundles ligeros.
- Diseña estados loading/empty/error/offline y reconexión.
- Minimiza peticiones, polling, transferencia y consumo de batería.
- Diferencia caché temporal, descarga offline y almacenamiento permanente.
- Para reproducción: valida cola, estado persistente, interrupciones, reconexión, autorización y expiración de URLs.
- La reproducción en segundo plano, especialmente en iOS, requiere validación en dispositivo real. No la declares funcional por pruebas de escritorio.

## Infraestructura
- Respeta la separación staging/producción y la arquitectura existente de Cloudflare y Render.
- Inspecciona Dockerfiles, workflows, bindings, variables y logs antes de cambiar despliegues.
- Nunca incluyas secretos, tokens, cookies, claves privadas ni credenciales en Git, logs o respuestas.
- No rotes secretos, borres recursos, ejecutes migraciones destructivas ni despliegues a producción sin aprobación explícita.
- Verifica health checks, logs y endpoints después de un despliegue autorizado.

## Seguridad y privacidad
- Aplica mínimo privilegio y validación server-side.
- Revisa IDOR, escalada de privilegios, inyección, SSRF, path traversal, abuso de API, cargas de archivos y exposición de secretos.
- No registres contraseñas, tokens, claves privadas ni datos sensibles.
- Distingue vulnerabilidades confirmadas de riesgos hipotéticos.

## Restricciones de conectividad
- Asume conexiones lentas, caras, con pérdida de paquetes y cambios Wi-Fi/móvil.
- Prioriza integridad, progreso recuperable, reintentos limitados, reanudación y tolerancia a fallos antes que velocidad máxima.
- Evita descargas repetidas y respuestas grandes. No hagas polling agresivo.

## Git y entrega
- No hagas push, merge, release ni despliegue sin aprobación explícita.
- No uses force push ni reescribas historia.
- No descartes cambios del usuario.
- Resume archivos modificados, tests ejecutados, resultados, riesgos y pasos manuales pendientes.
