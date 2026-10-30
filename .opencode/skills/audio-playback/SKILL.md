---
name: audio-playback
description: Diseña, depura y valida reproducción, cola, playlists, streaming y reproducción en segundo plano en KubanFy.
---

# Audio playback engineering

- Inspecciona primero el motor de audio y contratos API actuales.
- Separa resolución de metadata, preview, streaming, descarga offline y caché.
- Preserva cola, índice actual, progreso, repeat/shuffle y estado entre navegación cuando el producto lo requiera.
- Gestiona interrupciones, llamadas, auriculares, cambios de salida, pérdida de red y reanudación.
- Minimiza buffering excesivo y descargas repetidas.
- Valida URLs firmadas, autorización, expiración y errores de proveedor.
- Background audio en iOS depende de capacidades nativas, configuración de audio y ciclo de vida; prueba en dispositivo real.
- Crea tests automatizados para lógica de cola/estado y una lista de pruebas manuales para comportamiento del sistema operativo.
- No afirmes soporte de background playback solo porque el audio sigue activo en una pestaña de escritorio.
