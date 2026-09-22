# KubanFy Mobile

Aplicación **única** React Native (CLI + TypeScript) para:

| Modo | Quién | Qué hace |
|------|--------|----------|
| **Escuchar** | Todos los usuarios | Discovery, playlists, offline |
| **Artista** | Roles `ARTIST` / `ARTIST_MANAGER` | Catálogo, upload, publish |
| **Admin** | Roles admin/moderator/finance… | Flags, moderación, pagos |

El cambio de modo es solo de **UI**. **Toda autorización es del servidor** (JWT + RBAC). Un cliente modificado no puede elevar privilegios.

## Seguridad (decisión de producto)

Una sola app **no compromete** la seguridad si:

1. El API sigue validando permisos en cada ruta (`require_permissions`).
2. No se embebe lógica de “soy admin ⇒ permitido” en el cliente.
3. Acciones destructivas (takedown, suspend) dejan `audit_log` en backend.
4. Tokens en dispositivo con posible binding de device (ya en API).

Riesgo residual: la UI de admin viaja en el binario. Mitigación: no se muestran datos sensibles sin 200 del API; ofuscar no es control de acceso.

## Stack

- React Native **0.76** (CLI, **sin Expo** — offline / background audio / descargas nativas)
- TypeScript estricto
- React Navigation 7
- Zustand (auth)
- TanStack Query
- Design system dark-first (tokens en `src/theme`)

## Desarrollo

```bash
cd apps/mobile
npm install

# Android (emulador / dispositivo)
npm run android

# iOS (macOS + Xcode)
npm run ios
```

API local: por defecto `http://10.0.2.2:8000` (emulador Android). iOS simulador: `http://127.0.0.1:8000`.

```ts
(globalThis as any).KUBANFY_API_URL = 'https://api.staging.kubanfy.example';
```

## Builds de release (GitHub Actions)

Workflow: `.github/workflows/mobile-release.yml`

| Artefacto | Runner | Notas |
|-----------|--------|--------|
| **APK** (Android) | `ubuntu-latest` | Firmado con keystore en secrets |
| **IPA** (iOS) | `macos-latest` | Requiere Apple Developer + certificados |

### Secrets requeridos

**Android**

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

**iOS**

- `IOS_CERTIFICATE_P12_BASE64`
- `IOS_CERTIFICATE_PASSWORD`
- `IOS_PROVISIONING_PROFILE_BASE64`
- `APP_STORE_CONNECT_API_KEY` (opcional para TestFlight)

Hasta generar proyectos nativos (`android/`, `ios/`) con:

```bash
npx @react-native-community/cli init KubanFyTemp --version 0.76.5
# copiar carpetas android/ e ios/ y ajustar applicationId / bundleId
```

o `npx react-native@0.76.5 init` alineado a este `package.json`.

## Offline-first (siguiente iteración)

- Cola de eventos analytics offline
- Cache de audio cifrado (plan §45–47)
- Player con background audio nativo

## Estructura

```
src/
  api/           # cliente HTTP
  components/    # ModeSwitcher, …
  navigation/
  screens/
    auth/
    listener/
    artist/
    admin/
  store/
  theme/
  types/
  ui/
```
