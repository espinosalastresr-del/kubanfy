# Compilaciones móviles en GitHub Actions

Las builds de **APK** e **IPA** se ejecutan en GitHub Actions (no en máquinas locales obligatorias).

## Workflow

Archivo: `.github/workflows/mobile-release.yml`

| Trigger | Android APK | iOS IPA | GitHub Release |
|---------|-------------|---------|----------------|
| Tag `v*` | sí | sí | sí (APK adjunto) |
| `workflow_dispatch` | opcional | opcional | no |
| Push a `main` (cambios en `apps/mobile`) | sí (debug si no hay keystore) | no | no |

Si `android/` o `ios/` no están en el repo, el job **los genera en CI** con React Native CLI 0.76.

## Secrets (Settings → Secrets and variables → Actions)

### Android (APK firmado de release)

| Secret | Descripción |
|--------|-------------|
| `ANDROID_KEYSTORE_BASE64` | Keystore `.jks`/`.keystore` en base64 |
| `ANDROID_KEYSTORE_PASSWORD` | Password del store |
| `ANDROID_KEY_ALIAS` | Alias de la key |
| `ANDROID_KEY_PASSWORD` | Password de la key |

Sin estos secrets se publica **debug APK** (útil para smoke tests).

### iOS (IPA)

| Secret | Descripción |
|--------|-------------|
| `IOS_CERTIFICATE_P12_BASE64` | Certificado distribución `.p12` en base64 |
| `IOS_CERTIFICATE_PASSWORD` | Password del p12 |
| `IOS_PROVISIONING_PROFILE_BASE64` | Perfil `.mobileprovision` en base64 |

Runner: `macos-latest` (requerido por Xcode).

## Cómo disparar un release

```bash
git tag v0.1.0
git push origin v0.1.0
```

O Actions → **Mobile release** → Run workflow.

Artefactos: pestaña **Actions** → run → Artifacts (`kubanfy-android-*`, `kubanfy-ios-*`).

## API CI

Backend: `.github/workflows/ci.yml` (pytest + Alembic + Docker build de la API).
