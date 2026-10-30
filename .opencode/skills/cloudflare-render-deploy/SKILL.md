---
name: cloudflare-render-deploy
description: Diagnostica y prepara despliegues de KubanFy en Cloudflare y Render con controles de seguridad y rollback.
---

# Cloudflare and Render operations

1. Identifica servicio, entorno y rama exactos.
2. Inspecciona wrangler/config, Dockerfile, workflows, variables requeridas y logs.
3. Separa fallos de build, instalación de dependencias, runtime, red y secretos.
4. No imprimas ni copies secretos. Nunca guardes credenciales en Git.
5. Mantén staging separado de producción.
6. Antes de desplegar, resume cambios, impacto, comandos y rollback; pide aprobación.
7. Después, verifica resultado del deploy, logs, health/live, health/ready y endpoints relevantes.
8. No declares despliegue correcto solo porque CI compiló.
