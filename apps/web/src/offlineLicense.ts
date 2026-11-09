export type LocalOfflineLicense = {
  token: string;
  trackId: string;
  expiresAt: string;
  quality: string;
  contentHash: string;
  assetVersion: number;
  deviceId: string;
  source: "bootstrap" | "premium" | "auto";
  publicKeyPem?: string;
};

export type LocalOfflineTrack = {
  trackId: string;
  quality: string;
  contentHash: string;
  assetVersion: number;
  source: "bootstrap" | "premium" | "auto";
};

type JwtClaims = {
  sub?: unknown;
  iat?: unknown;
  exp?: unknown;
  jti?: unknown;
  type?: unknown;
  license_id?: unknown;
  device_id?: unknown;
  track_id?: unknown;
  asset_version?: unknown;
  quality?: unknown;
  content_hash?: unknown;
  [key: string]: unknown;
};

function decodeBase64Url(value: string): Uint8Array {
  if (!/^[A-Za-z0-9_-]+$/.test(value)) throw new Error("JWT base64url inválido.");
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function decodeJsonSegment<T>(value: string): T {
  return JSON.parse(new TextDecoder().decode(decodeBase64Url(value))) as T;
}

function decodePublicKeyPem(publicKeyPem: string): Uint8Array {
  const base64 = publicKeyPem
    .replace(/\\n/g, "\n")
    .replace(/-----BEGIN PUBLIC KEY-----/g, "")
    .replace(/-----END PUBLIC KEY-----/g, "")
    .replace(/\s/g, "");
  if (!base64 || !/^[A-Za-z0-9+/]+={0,2}$/.test(base64)) {
    throw new Error("La clave pública offline no tiene formato PEM válido.");
  }
  const binary = atob(base64);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

/** Verify RS256 and every local binding before allowing persistent offline playback. */
export async function verifyOfflineLicense(
  license: LocalOfflineLicense,
  track: LocalOfflineTrack,
  currentDeviceId: string,
  nowMs = Date.now(),
): Promise<JwtClaims> {
  if (track.source === "auto") {
    throw new Error("La caché automática no usa licencias persistentes.");
  }
  const publicKeyPem = license.publicKeyPem;
  if (!publicKeyPem?.trim()) {
    throw new Error("Falta la clave pública de la licencia offline. Conéctate y valida la licencia.");
  }
  if (license.source !== track.source || license.trackId !== track.trackId) {
    throw new Error("La licencia local no pertenece a este track.");
  }
  if (license.deviceId !== currentDeviceId) {
    throw new Error("La licencia local está vinculada a otro dispositivo.");
  }
  if (license.quality !== track.quality) {
    throw new Error("La calidad de la licencia no coincide con el audio local.");
  }
  if (
    license.contentHash.toLowerCase() !== track.contentHash.toLowerCase() ||
    license.assetVersion !== track.assetVersion
  ) {
    throw new Error("El hash o la versión del asset no coinciden con la licencia local.");
  }

  const expiryMs = Date.parse(license.expiresAt);
  if (!Number.isFinite(expiryMs) || expiryMs <= nowMs) {
    throw new Error("La licencia offline está vencida.");
  }

  const segments = license.token.split(".");
  if (segments.length !== 3 || segments.some((segment) => !segment)) {
    throw new Error("El token de licencia offline no es un JWT válido.");
  }
  const header = decodeJsonSegment<{ alg?: string; typ?: string }>(segments[0]);
  if (header.alg !== "RS256" || (header.typ && header.typ !== "JWT")) {
    throw new Error("La licencia offline debe usar RS256.");
  }

  let publicKey: CryptoKey;
  try {
    publicKey = await crypto.subtle.importKey(
      "spki",
      decodePublicKeyPem(publicKeyPem),
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
      false,
      ["verify"],
    );
  } catch {
    throw new Error("No se pudo importar la clave pública de la licencia offline.");
  }

  const signatureValid = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    publicKey,
    decodeBase64Url(segments[2]),
    new TextEncoder().encode(`${segments[0]}.${segments[1]}`),
  );
  if (!signatureValid) throw new Error("La firma RS256 de la licencia offline no es válida.");

  const claims = decodeJsonSegment<JwtClaims>(segments[1]);
  const nowSeconds = Math.floor(nowMs / 1000);
  if (
    claims.type !== "offline_license" ||
    typeof claims.sub !== "string" || !claims.sub ||
    typeof claims.jti !== "string" || !claims.jti ||
    typeof claims.license_id !== "string" || !claims.license_id ||
    typeof claims.iat !== "number" || !Number.isSafeInteger(claims.iat) ||
    typeof claims.exp !== "number" || !Number.isSafeInteger(claims.exp) ||
    typeof claims.asset_version !== "number" ||
    !Number.isSafeInteger(claims.asset_version)
  ) {
    throw new Error("Los claims obligatorios de la licencia offline son inválidos.");
  }
  if (claims.exp <= nowSeconds || claims.iat > nowSeconds + 60 || claims.exp <= claims.iat) {
    throw new Error("La licencia offline está vencida o tiene fechas inválidas.");
  }
  if (Math.abs(claims.exp - Math.floor(expiryMs / 1000)) > 2) {
    throw new Error("La expiración local no coincide con la licencia firmada.");
  }
  if (
    claims.device_id !== currentDeviceId ||
    claims.track_id !== track.trackId ||
    claims.asset_version !== track.assetVersion ||
    claims.quality !== track.quality ||
    typeof claims.content_hash !== "string" ||
    claims.content_hash.toLowerCase() !== track.contentHash.toLowerCase()
  ) {
    throw new Error("La licencia offline no corresponde a este dispositivo o asset.");
  }
  return claims;
}
