# KubanFy — migración móvil nativa

React Native queda retirado. El repositorio usa dos clientes independientes:
- Android: Kotlin + Android SDK.
- iOS: Swift + SwiftUI.

El backend FastAPI sigue siendo la fuente única de verdad. Compartimos contratos HTTP y reglas de seguridad, no un runtime multiplataforma.

La base nativa incluye navegación inicial, API/Keychain y CryptoKit AES-256-GCM en iOS. Android queda preparado para Android Keystore, AES-256-GCM, Media3/ExoPlayer y WorkManager.

CI independiente:
- Android: tests + APK debug.
- iOS: build de dispositivo sin firma + contenedor IPA como artefacto.

El IPA sin firma es un contenedor de distribución y no puede instalarse directamente hasta ser firmado con credenciales Apple válidas. La siguiente etapa porta autenticación, descubrimiento, biblioteca/playlists, reproducción, descargas offline/licencias y flujos de artista/admin en ambas plataformas en paralelo.
