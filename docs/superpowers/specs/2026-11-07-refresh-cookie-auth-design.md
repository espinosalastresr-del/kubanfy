# Diseño: autenticación web same-origin con refresh cookie

Fecha: 2026-11-07
Rama: security/refresh-cookie-auth
Base funcional: staging/canonical

## Objetivo

Eliminar el almacenamiento del refresh token en JavaScript y evitar que Safari/iOS dependa de cookies de terceros o de llamadas de autenticación entre los hosts de la web y la API. El navegador utilizará exclusivamente el origen de KubanFy Web para las peticiones API. El refresh token se almacenará en una cookie HttpOnly; Secure; SameSite=Lax, mientras que el access token seguirá en memoria.

Se conserva la autenticación Bearer existente para clientes no web y compatibilidad temporal durante la migración. Este cambio no requiere migrar usuarios ni invalidar sesiones existentes.

## Estado actual confirmado

- apps/web/src/api.ts usa VITE_API_BASE_URL con fallback al Worker de API y construye URLs absolutas.
- El refresh token se lee/escribe en sessionStorage con clave kubanfy.refresh.
- Login devuelve { user, tokens: { access_token, refresh_token, expires_in } }.
- POST /v1/auth/refresh exige actualmente RefreshRequest.refresh_token en JSON y rota/revoca la sesión anterior en AuthService.refresh.
- GET /v1/auth/me y las demás rutas protegidas aceptan Bearer mediante get_current_user.
- El logout web actual solo limpia tokens en el cliente; no revoca la sesión del servidor.
- apps/web/wrangler.jsonc define assets SPA y observabilidad, pero no tiene handler/proxy API ni binding de origen API.
- FastAPI permite CORS con credenciales y agrega explícitamente el origen staging web a la allowlist.

## Enfoques considerados

1. Proxy same-origin en el Worker web (elegido). El Worker sirve assets y reenvía /api/* al origen API, eliminando el salto de origen desde el navegador. Simplifica cookies, CORS y Safari. Añade una pequeña capa de proxy que debe ser estricta y no convertirse en open proxy.
2. Cookies cross-origin directas a la API. Menos cambios en el Worker, pero mantiene CORS con credenciales y dependencia del comportamiento de cookies entre hosts distintos. No resuelve de forma robusta el objetivo de reducir problemas de Safari.
3. Mantener refresh token en sessionStorage. Es el menor cambio, pero deja el secreto accesible a JavaScript/XSS y no corrige la arquitectura de orígenes.

## Flujo propuesto

### Web

1. Todas las llamadas de la aplicación usan rutas relativas /api/v1/....
2. El Worker web intercepta /api/*, reenvía a un único API_ORIGIN configurado y elimina solo el prefijo /api antes de enviar al backend.
3. El proxy conserva método, query string, headers necesarios, body en streaming, status y headers de respuesta. No registra cookies, Authorization ni cuerpos de autenticación.
4. El navegador no conoce el host API ni hace peticiones directas a él.
5. Login web devuelve usuario y access token, pero no incluye refresh token en JSON. La respuesta establece la cookie HttpOnly.
6. Refresh envía la cookie automáticamente y devuelve un access token nuevo; la rotación sustituye la cookie.
7. Access token permanece solo en memoria. Al recargar, el cliente llama refresh y después /me.
8. Logout revoca la sesión asociada al refresh token y expira la cookie usando los mismos atributos.

### API / compatibilidad

- Identificar el flujo web por un Origin exactamente igual a un origen permitido, no por un header arbitrario controlado por el cliente.
- Login desde origen web: establece cookie y omite refresh token del JSON. Login Bearer/legacy sin origen web mantiene la respuesta actual.
- Refresh desde origen web: acepta cookie; rechaza ausencia de Origin, Origin no permitido y tokens ambiguos. El cliente legacy puede seguir enviando JSON como hoy.
- Añadir logout web que revoca la sesión del refresh token y borra cookie. No debe convertir logout en cierre de todas las sesiones.
- Mantener get_current_user Bearer para las rutas protegidas en esta fase. No introducir cookies de access token.
- El refresh token debe seguir siendo de un solo uso por rotación; el replay de una sesión revocada debe fallar.
- Cookie host-only (sin Domain), Path /api/v1/auth, HttpOnly, Secure, SameSite=Lax, Max-Age alineado con la duración configurada. El proxy no debe reescribir Set-Cookie de manera insegura.
- La cookie solo se utiliza en refresh/logout; no se envía a endpoints de negocio fuera de ese Path.

## CSRF, CORS y límites de confianza

- Refresh y logout basados en cookie validan Origin contra una allowlist exacta de orígenes web.
- Métodos mutables que continúan autenticados por Bearer no deben aceptar autenticación implícita mediante cookie.
- SameSite=Lax es defensa adicional, no reemplaza la comprobación Origin.
- No se permite Access-Control-Allow-Origin: * con credenciales.
- El backend no debe confiar en X-Forwarded-For ni en headers de identidad añadidos por el navegador. El Worker elimina headers hop-by-hop y cualquier header interno reservado antes de construir la petición upstream.
- El proxy acepta solo el prefijo fijo /api/; no acepta destinos, hosts o rutas upstream suministrados por el usuario.
- Se mantiene la allowlist CORS explícita para integraciones no web que realmente la necesiten; el flujo same-origin no depende de CORS.

## Configuración

- Worker web: variable no secreta API_ORIGIN con el origen HTTPS de la API de staging. Debe ser un origen fijo y validado, sin path ni query.
- Backend: lista explícita de orígenes web permitidos (reutilizar o normalizar la configuración existente de CORS, sin duplicar allowlists divergentes).
- Cookie Secure obligatorio en staging/producción HTTPS. Desarrollo local puede tener un modo explícito sin Secure únicamente para localhost.
- Documentar las variables requeridas y valores de ejemplo no secretos. No cambiar secretos ni variables remotas en esta tarea.

## Migración de navegador

- Dejar de leer y escribir kubanfy.refresh.
- Borrar una sola vez la clave legacy sessionStorage.kubanfy.refresh al inicializar para retirar el secreto antiguo del navegador.
- No borrar kubanfy.device, localStorage de dispositivo ni cookie kubanfy_device; son identificadores, no credenciales.
- No limpiar sesión local en un fallo transitorio de red. Diferenciar 401 definitivo de errores de conectividad/5xx.
- Coordinar refresh concurrente con una promesa compartida para evitar que varias peticiones roten el mismo refresh token simultáneamente.

## Alcance y exclusiones

Incluye Worker web, backend FastAPI, cliente React, documentación y pruebas automatizadas. Incluye rotación, logout, validación Origin, compatibilidad legacy, boot/reload y concurrencia.

No incluye rediseño visual, cambios de base de datos salvo que la implementación revele una necesidad real, cambios de políticas de sesiones/dispositivos, despliegue, cambios de DNS, edición de variables remotas, ni validación de audio en segundo plano iOS.

## Pruebas de aceptación

1. Login web emite cookie con todos los atributos requeridos y no devuelve refresh token en JSON.
2. Login legacy conserva el contrato Bearer actual.
3. Refresh con cookie válida rota la sesión y emite nueva cookie; el token anterior no vuelve a funcionar.
4. Refresh sin cookie, Origin ausente o Origin no permitido falla sin mutar sesión.
5. Logout revoca la sesión actual y expira la cookie; logout no afecta otras sesiones.
6. Replay/reuse de refresh token revocado falla.
7. La API sigue aceptando Bearer en rutas protegidas.
8. El cliente no guarda refresh token en localStorage/sessionStorage; la clave antigua se elimina.
9. Al recargar, la sesión se recupera con refresh cookie y access token nuevo.
10. Refresh concurrente comparte una sola operación y evita carreras de rotación.
11. El proxy conserva status, query, headers relevantes y streaming; rechaza rutas fuera del prefijo y no expone un proxy arbitrario.
12. Tests de backend, tests de cliente/Worker, typecheck y build pasan.

## Decisiones pendientes del implementador

- Confirmar los patrones de tests disponibles y la forma de ejecutar pruebas Worker sin añadir dependencias innecesarias.
- Confirmar el upstream de staging como https://kubanfy-api-staging.globumlatinmusic.workers.dev frente a Render directo; por defecto se usará el Worker API existente porque es el endpoint que usa hoy el cliente.
- Confirmar cómo el backend distingue web vs legacy: Origin exacto validado en rutas login/refresh/logout; no se confiará en un marcador enviado por el cliente.
- Si la rotación simultánea actual no tiene atomicidad suficiente, añadir protección acotada para el flujo de refresh sin cambiar la política general de sesiones.

## Riesgos y mitigaciones

- Proxy incorrecto: pruebas de contrato y streaming; upstream fijo.
- CSRF: cookie solo para refresh/logout, SameSite=Lax y Origin exacto.
- Pérdida de sesión al recargar: boot refresh-first y pruebas E2E.
- Carreras de refresh: single-flight en cliente y test de reuso concurrente; revisar la transacción del servicio.
- Compatibilidad móvil/legacy: no cambiar el esquema Bearer existente fuera del flujo web.
- Pruebas incompletas de Safari real: automatización web no sustituye una prueba manual en Safari/iOS; dejarlo explícito como validación pre-release.
