# KubanFy Web/PWA — Plan Técnico

Estado: propuesta técnica inicial
Prioridad: Web/PWA
Rama: feat/release-track-management
Backend: FastAPI existente
Cliente móvil nativo: fuera de prioridad; se podrá adaptar posteriormente a este contrato

## 1. Objetivo

Construir el cliente principal de KubanFy como una Web App instalable (PWA), optimizada desde el primer día para:

- Cuba y redes móviles inestables.
- Alto RTT, pérdida de paquetes y cambios Wi-Fi/4G.
- Bajo consumo de datos.
- Uso offline parcial.
- Reproducción progresiva de audio.
- Cache cifrada.
- Descargas Premium cifradas.
- Respeto estricto de las reglas de entitlement y antipiratería del backend.

La PWA no será una versión simplificada de la app iOS. Será el cliente de referencia de KubanFy. Las futuras aplicaciones iOS/Android deberán adaptarse al contrato de esta arquitectura, no al revés.

## 2. Reglas de negocio que no pueden cambiar

### FREE

- Streaming exclusivamente LOW.
- LOW = 128 kbps.
- No puede seleccionar MEDIUM ni LOSSLESS.
- Publicidad.
- Cache automática de máximo 3 canciones.
- La cache automática usa LOW.
- No existen descargas persistentes explícitas.

### PREMIUM

- Streaming MEDIUM = 320 kbps.
- Sin publicidad.
- Descargas persistentes ilimitadas, cifradas.
- Cache automática en la misma calidad que se está reproduciendo.
- La cache automática y las descargas explícitas son mecanismos distintos.

### FAMILY / STUDENT

- Heredan las ventajas Premium.
- Streaming MEDIUM = 320 kbps.
- Sin publicidad.
- Descargas.
- Cache automática.

### Calidad

La aplicación utilizará las capacidades lógicas:

- LOW
- MEDIUM
- LOSSLESS

Nunca se codificará la lógica de negocio como FREE_128 o PREMIUM_320.

El backend seguirá siendo la autoridad para entitlement, calidad, autorización, hashes, versión de contenido y URLs firmadas.

## 3. Arquitectura general

```
                    ┌───────────────────────────┐
                    │       KubanFy API         │
                    │ FastAPI + Auth + Playback │
                    └─────────────┬─────────────┘
                                  │
                         HTTPS / REST / R2
                                  │
                    ┌─────────────▼─────────────┐
                    │          Web/PWA           │
                    │ React + TypeScript + Vite │
                    └─────────────┬─────────────┘
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
       ┌─────▼─────┐       ┌──────▼──────┐      ┌─────▼──────┐
       │ UI / App  │       │ Audio Engine │      │ Sync/Cache │
       └───────────┘       └──────┬──────┘      └─────┬──────┘
                                  │                    │
                           ┌──────▼──────┐      ┌──────▼──────┐
                           │ MSE / audio │      │ IndexedDB   │
                           │ pipeline    │      │ + Cache API │
                           └─────────────┘      └─────────────┘
```

## 4. Stack inicial

- TypeScript.
- React.
- Vite.
- pnpm.
- PWA mediante Service Worker.
- IndexedDB para datos estructurados y audio cifrado.
- Cache Storage para shell estático y recursos HTTP apropiados.
- MediaSource Extensions (MSE) para reproducción progresiva cuando el codec/container sea compatible.
- Fetch + HTTP Range para recuperación parcial y reanudación.
- Web Crypto API para operaciones criptográficas del cliente.
- Web Workers/Dedicated Workers para trabajo pesado que no debe bloquear la UI.

Dependencias deberán mantenerse al mínimo. No se añadirá una librería para resolver algo que pueda resolverse con APIs nativas de forma fiable.

## 5. Arquitectura de carpetas propuesta

```
web/
├── public/
│   ├── icons/
│   ├── manifest.webmanifest
│   └── ...
├── src/
│   ├── app/
│   │   ├── router/
│   │   ├── providers/
│   │   └── bootstrap/
│   ├── components/
│   ├── features/
│   │   ├── auth/
│   │   ├── catalog/
│   │   ├── search/
│   │   ├── library/
│   │   ├── player/
│   │   ├── downloads/
│   │   ├── cache/
│   │   ├── account/
│   │   └── connectivity/
│   ├── audio/
│   │   ├── kby2/
│   │   ├── range/
│   │   ├── decrypt/
│   │   ├── mse/
│   │   └── playback/
│   ├── api/
│   │   ├── client.ts
│   │   ├── auth.ts
│   │   ├── music.ts
│   │   ├── offline.ts
│   │   └── types.ts
│   ├── storage/
│   │   ├── db.ts
│   │   ├── tracks.ts
│   │   ├── chunks.ts
│   │   ├── downloads.ts
│   │   └── cache-policy.ts
│   ├── sync/
│   ├── network/
│   ├── telemetry/
│   ├── workers/
│   ├── sw/
│   ├── styles/
│   └── main.tsx
├── tests/
├── package.json
├── pnpm-lock.yaml
└── vite.config.ts
```

La estructura podrá ajustarse después de inspeccionar el repositorio actual, pero los límites entre UI, API, audio y almacenamiento deben mantenerse.

## 6. Contrato con el backend

La PWA consumirá el backend existente. No duplicará reglas de negocio.

Debe utilizar:

- autenticación existente;
- catálogo existente;
- entitlement existente;
- endpoint de playback;
- autorización de reproducción;
- heartbeat/anti-fraud;
- content_hash;
- asset version;
- quality;
- signed URLs;
- endpoints offline existentes y los que sean necesarios para el nuevo flujo.

La aplicación solicitará explícitamente KBY v2 para el nuevo pipeline.

El backend debe seguir rechazando cualquier combinación de calidad o asset que el usuario no pueda utilizar.

## 7. KBY v2 y reproducción progresiva

KBY v2 será la base criptográfica del nuevo cliente.

Cada contenedor contiene:

- header;
- content hash;
- tamaño de plaintext;
- calidad;
- content type;
- tamaño de chunk;
- número de chunks;
- chunks AES-256-GCM independientes;
- nonce independiente por chunk;
- autenticación GCM por chunk.

Flujo:

```
play(track)
   │
   ├── request playback authorization
   │
   ├── obtain signed KBY2 URL
   │
   ├── request KBY2 header/range
   │
   ├── calculate required chunk ranges
   │
   ├── download encrypted chunks
   │
   ├── authenticate + decrypt chunk
   │
   ├── persist encrypted chunk
   │
   └── feed plaintext media bytes to playback pipeline
```

Nunca se persistirá audio PCM/MP4 en claro como mecanismo normal de cache.

## 8. Gate técnico obligatorio del pipeline de audio

Antes de implementar el reproductor definitivo debemos inspeccionar los derivados LOW/MEDIUM actuales.

KBY2 cifra bytes de un archivo; no convierte automáticamente un MP4 normal en un stream MSE.

Debemos determinar:

1. si los derivados actuales son fragmented MP4;
2. codec exacto;
3. MIME exacto;
4. estructura moov/moof/mdat;
5. posibilidad de reproducción incremental con MSE;
6. comportamiento de seeking;
7. comportamiento en Safari/iOS, Chrome Android y Chromium desktop.

Si los derivados actuales no son adecuados, el backend deberá generar un formato de reproducción web apropiado, preferentemente fMP4 compatible con MSE.

No se implementará un hack de cliente que dependa de que un MP4 completo esté disponible.

## 9. Audio engine

El Audio Engine será independiente de React.

Responsabilidades:

- autorización de playback;
- negociación de calidad;
- descarga por Range;
- parser KBY2;
- validación de header;
- derivación/obtención segura de la clave;
- descifrado de chunks;
- cola de chunks;
- buffering;
- backpressure;
- retries;
- reanudación;
- detección de conectividad;
- integración con MSE;
- seeking;
- métricas de reproducción.

Estados:

```
IDLE
AUTHORIZING
FETCHING_HEADER
BUFFERING
PLAYING
STALLED
RECONNECTING
SEEKING
PAUSED
ENDED
ERROR
```

El reproductor nunca descargará intencionalmente una canción completa antes de comenzar a reproducir.

## 10. Estrategia de buffering

No se utilizará un buffer gigante.

Objetivo inicial:

- comenzar reproducción con el mínimo de datos viable;
- mantener una ventana pequeña de datos futuros;
- ampliar temporalmente la ventana ante buena conectividad;
- reducirla ante pérdida de paquetes/RTT elevado;
- detener descargas cuando el buffer sea suficiente.

Se medirán:

- RTT;
- throughput estimado;
- tiempo hasta primer byte;
- tiempo hasta primer audio;
- buffer ahead;
- rebuffer count;
- bytes descargados;
- bytes reproducidos;
- retries;
- Range failures.

Esto permitirá optimizar específicamente para conexiones cubanas.

## 11. Cache automática

La cache automática es temporal y administrada por política.

### FREE

- máximo 3 tracks;
- LOW únicamente;
- política LRU;
- el track actualmente reproduciéndose no se elimina;
- al insertar el cuarto track se elimina el menos recientemente utilizado;
- si el almacenamiento falla, playback online debe continuar.

### PREMIUM / FAMILY / STUDENT

- cache automática en la calidad actualmente reproducida;
- no convertir MEDIUM a LOW para ahorrar espacio;
- respetar la calidad que realmente autorizó el backend;
- política de almacenamiento configurable;
- LRU cuando se alcanza el límite local;
- el usuario podrá borrar cache sin borrar descargas explícitas.

## 12. Descargas explícitas Premium

Las descargas son diferentes de la cache automática.

Modelo:

```
automatic cache
    = temporary + policy-managed

explicit download
    = persistent + user-requested + encrypted
```

Cada descarga tendrá:

- track_id;
- asset version;
- quality;
- content_hash;
- encrypted KBY2 data;
- estado;
- bytes disponibles;
- fecha;
- tamaño;
- integridad;
- entitlement snapshot mínimo necesario para gestión local.

Una descarga incompleta nunca se presentará como disponible offline.

## 13. IndexedDB

IndexedDB almacenará metadata, índices y chunks cifrados.

Entidades principales:

### tracks

- trackId
- version
- contentHash
- quality
- duration
- title
- artist
- artwork reference
- cacheMode
- lastAccessedAt

### chunks

- trackId
- version
- quality
- chunkIndex
- encryptedBytes
- plaintextLength
- nonce
- verified
- downloadedAt

### downloads

- trackId
- version
- quality
- contentHash
- status
- completedChunks
- totalChunks
- totalBytes
- createdAt
- updatedAt

### playback_state

- queue
- currentTrack
- position
- timestamp
- volume
- repeat/shuffle state

No se guardarán tokens de acceso de larga duración en IndexedDB.

## 14. Cache Storage

Cache Storage se utilizará principalmente para:

- HTML shell;
- JavaScript;
- CSS;
- iconos;
- manifest;
- imágenes públicas apropiadas;
- respuestas GET pequeñas y cacheables.

No será el almacenamiento principal del audio cifrado por chunks.

Service Worker + Cache Storage proporcionarán el shell offline, mientras IndexedDB administrará los datos y audio cifrado.

## 15. Service Worker

Funciones:

- precache del app shell;
- actualización controlada;
- cache de assets estáticos;
- fallback offline;
- limpieza de versiones antiguas;
- coordinación limitada con la aplicación.

El Service Worker no decidirá entitlement ni autorización de audio.

Tampoco deberá interceptar indiscriminadamente URLs firmadas de R2.

## 16. Autenticación

Objetivo:

- access token de corta duración;
- refresh mediante mecanismo seguro soportado por backend;
- evitar tokens permanentes en localStorage;
- recuperación de sesión tras reinicio;
- logout que invalide el estado local sensible;
- separación entre guest y usuario autenticado.

Guest:

- streaming online;
- LOW;
- sin cache;
- sin descargas;
- URLs de corta duración.

La UI puede recordar preferencias no sensibles localmente.

## 17. API client

Debe incluir:

- timeout;
- AbortController;
- retry únicamente para operaciones seguras;
- exponential backoff;
- Retry-After;
- ETag/If-None-Match;
- manejo 401;
- manejo 403;
- manejo 404;
- manejo 408/429;
- manejo 5xx;
- detección de offline;
- correlation/request IDs cuando el backend los proporcione.

No se harán retries agresivos en conexiones móviles.

## 18. Sincronización offline

La aplicación debe funcionar aunque el backend esté temporalmente inaccesible.

Offline:

- mostrar shell;
- mostrar biblioteca local;
- mostrar descargas válidas;
- reproducir cache válida;
- reproducir descargas válidas;
- mostrar estado de conectividad;
- acumular operaciones seguras para sincronizar posteriormente.

Al recuperar red:

1. refrescar sesión si corresponde;
2. validar cambios de catálogo;
3. sincronizar metadata;
4. actualizar artwork;
5. procesar operaciones pendientes;
6. actualizar estado de cache/downloads;
7. evitar descargar datos que ya existan.

Background Sync se considerará una mejora y nunca será requisito crítico para el funcionamiento básico.

## 19. Catálogo

Carga progresiva:

- primera pantalla pequeña;
- paginación por cursor;
- imágenes pequeñas;
- lazy loading;
- metadata compacta;
- ETag/304;
- cache local;
- actualización incremental.

No descargar el catálogo completo al abrir la aplicación.

## 20. UI/UX mobile-first

Pantallas principales:

- Inicio;
- Buscar;
- Biblioteca;
- Descargas;
- Reproductor;
- Cuenta;
- Configuración;
- Diagnóstico/conectividad.

El reproductor deberá ser persistente y accesible desde cualquier pantalla.

Controles:

- play/pause;
- siguiente/anterior;
- seek;
- repeat;
- shuffle;
- favorite;
- download cuando corresponda;
- información de calidad;
- estado offline/cache.

No se mostrará información técnica innecesaria al usuario normal.

## 21. Data Saver

Modo Data Saver:

- fuerza LOW para usuarios autorizados que puedan utilizar LOW;
- reduce precarga;
- reduce artwork;
- evita prefetch agresivo;
- limita sincronización;
- conserva reproducción;
- muestra consumo aproximado.

No puede utilizarse para conceder calidad superior al entitlement del usuario.

## 22. Antipiratería

Principios obligatorios:

- audio persistente siempre cifrado;
- URLs firmadas de corta duración;
- autorización server-side;
- entitlement server-side;
- device/session binding cuando el backend lo requiera;
- content hash;
- asset version;
- integridad de chunks;
- sin audio plaintext persistente;
- no confiar en flags de cliente para determinar Premium;
- no permitir cambiar quality localmente para obtener MEDIUM;
- downloads sólo mediante autorización válida;
- telemetry de reproducción y abuso.

La seguridad del cliente es un mecanismo de defensa adicional, no la autoridad.

## 23. Observabilidad

El cliente tendrá un logger estructurado con:

- session ID no sensible;
- request ID;
- track ID;
- quality;
- KBY version;
- chunk index;
- network state;
- RTT;
- buffer;
- playback state;
- error classification.

Nunca:

- access tokens;
- refresh tokens;
- signed URLs completas;
- claves criptográficas;
- datos personales innecesarios.

Se podrá exportar un diagnóstico para soporte.

## 24. Pruebas

### Unitarias

- parser KBY2;
- cálculo de offsets;
- AES-GCM;
- detección de corrupción;
- Range planner;
- cache LRU;
- entitlement mapping;
- download state machine;
- retry policy;
- offline state machine.

### Integración

- API auth;
- playback authorization;
- KBY2 header;
- Range requests;
- expiración de signed URL;
- cambio de calidad;
- cache durante playback;
- descarga reanudable;
- corrupción de chunk;
- pérdida de red;
- reconexión.

### E2E

Escenarios mínimos:

1. guest reproduce LOW;
2. FREE intenta MEDIUM y backend lo rechaza;
3. FREE reproduce cuatro canciones y sólo quedan tres en cache;
4. Premium reproduce MEDIUM y cachea MEDIUM;
5. Premium descarga una canción;
6. descarga interrumpida y reanudada;
7. reproducción sin conexión desde cache;
8. reproducción sin conexión desde descarga;
9. signed URL expira durante playback;
10. red cambia Wi-Fi -> 4G;
11. RTT alto;
12. pérdida de paquetes;
13. almacenamiento insuficiente;
14. navegador elimina almacenamiento;
15. logout;
16. cambio de entitlement.

## 25. Pruebas de conectividad

El laboratorio de QA deberá simular como mínimo:

- 100 kbps;
- 250 kbps;
- 500 kbps;
- 1 Mbps;
- RTT 100 ms;
- RTT 250 ms;
- RTT 500 ms;
- pérdida 1%;
- pérdida 5%;
- desconexión temporal;
- cambio de red.

Objetivo: que una conexión mala degrade la experiencia de forma controlada en lugar de producir errores catastróficos.

## 26. Compatibilidad objetivo

Primera línea:

- Safari moderno en iPhone/iPad;
- Chrome Android;
- Chrome/Edge/Firefox desktop.

La compatibilidad se basará en feature detection.

No se asumirá que una API multimedia funciona sólo porque existe el objeto global.

MSE y codecs serán comprobados mediante capacidades reales del navegador antes de seleccionar el pipeline.

## 27. Persistencia del almacenamiento

El cliente debe consultar cuota/uso cuando sea posible y solicitar almacenamiento persistente cuando corresponda.

El almacenamiento del navegador puede ser evictable y la aplicación debe tolerar esa situación.

Por ello:

- cache automática puede desaparecer y reconstruirse;
- descargas deben detectarse como incompletas si faltan chunks;
- metadata debe permitir reconstrucción;
- nunca marcar una descarga como disponible únicamente por existir su registro.

## 28. Deployment

Inicialmente:

- Render Static Site;
- CDN;
- HTTPS;
- dominio web de KubanFy;
- auto-deploy desde GitHub;
- build con pnpm;
- artefactos pequeños.

El backend continuará en Render como servicio separado.

No se introducirá un backend Node adicional salvo que exista una necesidad concreta.

## 29. CI/CD web

Workflow separado:

- install con pnpm;
- lockfile obligatorio;
- lint;
- typecheck;
- unit tests;
- build;
- PWA validation;
- E2E en CI;
- bundle-size check;
- deploy Render.

El CI del backend seguirá siendo independiente.

## 30. Orden de implementación

### Fase A — Contrato y auditoría

- inspeccionar API actual;
- inspeccionar KBY v1;
- inspeccionar KBY2;
- inspeccionar derivados reales;
- confirmar codec/container;
- documentar endpoints;
- identificar gaps.

### Fase B — Audio backend

- completar KBY2;
- corregir cualquier bug de dual-write;
- backfill de catálogo;
- garantizar Range;
- verificar signed URLs;
- preparar derivados compatibles con streaming web;
- tests de integración.

### Fase C — Web shell

- crear proyecto web;
- React/TypeScript/Vite;
- routing;
- diseño mobile-first;
- manifest;
- Service Worker;
- Render Static Site;
- CI.

### Fase D — Datos y auth

- API client;
- auth;
- catálogo;
- biblioteca;
- cache metadata;
- IndexedDB.

### Fase E — Audio engine

- KBY2 parser;
- Range planner;
- decrypt;
- MSE;
- buffering;
- reconexión;
- métricas.

### Fase F — Cache/downloads

- FREE LRU 3;
- Premium automatic cache;
- explicit downloads;
- resume;
- integrity;
- storage management.

### Fase G — UX completa

- player;
- search;
- library;
- account;
- settings;
- ads;
- diagnostics.

### Fase H — QA de conectividad

- throttling;
- RTT;
- packet loss;
- offline;
- network switching;
- storage eviction.

### Fase I — Usuarios reales

El producto web será la versión principal.

Sólo después de obtener usuarios reales y datos de uso se decidirá qué capacidades justifican continuar con iOS/Android.

## 31. Criterio de terminado del MVP

No se considerará listo sólo porque "la página carga".

El MVP deberá poder:

- iniciar sesión;
- navegar catálogo;
- buscar;
- reproducir progresivamente;
- respetar calidad por entitlement;
- funcionar con mala conectividad;
- cachear según plan;
- reproducir cache offline;
- permitir descargas Premium;
- reanudar descargas;
- mantener audio cifrado;
- sobrevivir a reconexiones;
- mostrar errores útiles;
- instalarse como PWA;
- actualizarse sin romper almacenamiento;
- pasar CI y E2E.

## 32. Decisión arquitectónica clave

La aplicación web será el cliente de referencia.

La prioridad queda:

1. Backend + protocolo de reproducción web.
2. Web/PWA.
3. Usuarios reales.
4. Métricas y feedback.
5. Sólo entonces adaptación de iOS/Android.

La aplicación iOS actual se considera temporal/obsoleta para esta etapa y no debe condicionar el nuevo diseño.
