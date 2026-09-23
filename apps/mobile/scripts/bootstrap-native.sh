#!/usr/bin/env bash
# Generate android/ and ios/ for KubanFy (React Native 0.76.x CLI — no Expo).
# Run on a machine with Node 20+, JDK 17, Android SDK; macOS + Xcode for iOS.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RN_VERSION="0.76.5"
TMP_DIR="$(mktemp -d)"
APP_NAME="KubanFyNative"

echo "==> Scaffolding temporary RN ${RN_VERSION} project in ${TMP_DIR}"
npx --yes @react-native-community/cli@15.1.3 init "$APP_NAME" \
  --version "$RN_VERSION" \
  --skip-install \
  --pm npm \
  --directory "$TMP_DIR/$APP_NAME"

if [[ ! -d "$ROOT/android" ]]; then
  echo "==> Copying android/"
  cp -R "$TMP_DIR/$APP_NAME/android" "$ROOT/android"
fi

if [[ ! -d "$ROOT/ios" ]]; then
  echo "==> Copying ios/"
  cp -R "$TMP_DIR/$APP_NAME/ios" "$ROOT/ios"
fi

# Align application id / display name where templates allow
if [[ -f "$ROOT/android/app/build.gradle" ]]; then
  sed -i.bak 's/applicationId "com\.[^"]*"/applicationId "com.kubanfy.app"/' \
    "$ROOT/android/app/build.gradle" || true
  rm -f "$ROOT/android/app/build.gradle.bak"
fi

echo "==> Installing JS dependencies"
npm install

if [[ "$(uname)" == "Darwin" ]] && [[ -d "$ROOT/ios" ]]; then
  echo "==> pod install"
  (cd ios && pod install)
fi

echo "==> Cleanup temp"
rm -rf "$TMP_DIR"

echo ""
echo "Done. Next:"
echo "  npm run android   # requires emulator/device"
echo "  npm run ios       # macOS only"
echo "  Link react-native-fs + react-native-track-player for full offline audio"
echo ""
