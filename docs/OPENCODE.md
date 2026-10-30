# OpenCode Desktop — configuración de KubanFy

Esta configuración vive en el repositorio para que todos los colaboradores utilicen las mismas instrucciones, agentes, skills y comandos. No contiene credenciales ni fija un modelo que quizá no esté disponible para la cuenta conectada.

## Primera apertura

1. Clona el repositorio y abre la carpeta raíz `kubanfy` en OpenCode Desktop (no abras solamente `apps/api`).
2. Comprueba que OpenCode detecta `opencode.json`, `AGENTS.md` y los agentes de `.opencode/agents/`.
3. Abre el selector de proveedor / ejecuta `/connect`, elige **OpenAI** y completa el método de autenticación que OpenCode ofrezca para tu cuenta.
4. Abre `/models` y selecciona un modelo OpenAI que aparezca disponible en esa cuenta. El modelo elegido se puede establecer como predeterminado desde el selector/configuración de OpenCode.
5. No guardes API keys, cookies OAuth, access tokens ni archivos `auth.json` en este repositorio.

## Importante sobre el acceso a modelos

La disponibilidad depende del método de autenticación, del plan y de los permisos de la cuenta. La documentación actual de OpenCode indica acceso con ChatGPT Plus/Pro mediante inicio de sesión ChatGPT; el uso de una API key de OpenAI se factura por separado según la cuenta API. No presupongas que ChatGPT Free incluye uso de modelos en OpenCode. Si el método OAuth no aparece o la cuenta no tiene entitlement, no intentes reutilizar cookies de navegador ni extraer sesiones: utiliza un método oficial disponible o deja la selección de modelo pendiente.

Documentación: https://opencode.ai/docs/providers/

## Agentes

- `build`: agente principal para implementar cambios.
- `@architect`: análisis y planes de arquitectura, sin editar.
- `@backend`: FastAPI, Pydantic, SQLAlchemy y PostgreSQL.
- `@frontend`: PWA/clientes, UI y audio.
- `@infrastructure`: Cloudflare, Render, Docker y CI/CD.
- `@security-reviewer`: revisión de solo lectura.

Los agentes secundarios heredan el modelo del agente principal si no se configura uno explícitamente. Por eso no se fijan modelos por agente: primero autentica OpenAI y elige un modelo que realmente esté disponible.

## Skills incluidas

OpenCode carga estas skills bajo demanda:

- `kubanfy-architecture`
- `backend-development`
- `pwa-mobile-performance`
- `audio-playback`
- `cloudflare-render-deploy`
- `database-migrations`
- `production-audit`

## Comandos del proyecto

- `/audit`: diagnóstico de solo lectura.
- `/validate`: ejecuta validaciones pertinentes del cambio actual.
- `/next-feature`: recomienda un único siguiente bloque priorizado.

## Flujo recomendado

1. `/audit` para conocer el estado real.
2. `@architect` para diseñar un cambio acotado.
3. `build`, `@backend` o `@frontend` para implementarlo.
4. `/validate` para ejecutar las pruebas.
5. `@security-reviewer` para revisar el diff.
6. `@infrastructure` para preparar un despliegue; solicita aprobación antes de ejecutar cualquier cambio remoto.

## Seguridad operativa

La configuración pide aprobación para comandos de terminal y accesos fuera del directorio del proyecto. No apruebes comandos de borrado, force push, despliegues, migraciones productivas o rotación de secretos sin revisar su alcance.
