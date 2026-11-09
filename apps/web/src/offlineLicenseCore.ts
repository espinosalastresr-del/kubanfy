export type OfflineLicenseExpectations = {
  userId: string;
  deviceId: string;
  trackId: string;
  quality: string;
  contentHash: string;
  assetVersion: number;
  expiresAt: string;
};

export type OfflineLicenseVerificationKey = {
  algorithm: "RS256";
  key_id: string;
  public_key: string;
};

function decodeBase64Url(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

function decodeJsonSegment(segment: string): Record<string, unknown> {
  return JSON.parse(new TextDecoder().decode(decodeBase64Url(segment))) as Record<string, unknown>;
}

function pemToDer(pem: string): ArrayBuffer {
  const body = pem
    .replace(/-----BEGIN PUBLIC KEY-----/g, "")
    .replace(/-----END PUBLIC KEY-----/g, "")
    .replace(/\s+/g, "");
  if (!body || body.length > 8192) throw new Error("Clave pública offline inválida.");
  const decoded = decodeBase64Url(body.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, ""));
  const copy = new Uint8Array(decoded.byteLength);
  copy.set(decoded);
  return copy.buffer;
}

export async function verifyOfflineLicenseToken(
  token: string,
  expected: OfflineLicenseExpectations,
  keys: OfflineLicenseVerificationKey[],
): Promise<void> {
  const segments = token.split(".");
  if (segments.length !== 3 || segments.some((segment) => !segment)) {
    throw new Error("La licencia offline no tiene un formato válido.");
  }
  let header: Record<string, unknown>;
  let claims: Record<string, unknown>;
  try {
    header = decodeJsonSegment(segments[0]);
    claims = decodeJsonSegment(segments[1]);
  } catch {
    throw new Error("No se pudo leer la licencia offline.");
  }
  if (header.alg !== "RS256" || (header.typ !== undefined && header.typ !== "JWT")) {
    throw new Error("La licencia offline utiliza un algoritmo no permitido.");
  }

  const now = Date.now();
  const expiry = Number(claims.exp);
  const issuedAt = Number(claims.iat);
  if (
    !Number.isFinite(expiry) || expiry * 1000 <= now ||
    !Number.isFinite(issuedAt) || issuedAt * 1000 > now + 60_000
  ) {
    throw new Error("La licencia offline ha vencido o tiene fechas inválidas.");
  }
  const storedExpiry = Date.parse(expected.expiresAt);
  if (!Number.isFinite(storedExpiry) || Math.abs(storedExpiry - expiry * 1000) > 5000) {
    throw new Error("La expiración de la licencia local no coincide con el token firmado.");
  }

  const required: Record<string, unknown> = {
    type: "offline_license",
    sub: expected.userId,
    device_id: expected.deviceId,
    track_id: expected.trackId,
    quality: expected.quality,
    content_hash: expected.contentHash,
    asset_version: expected.assetVersion,
  };
  for (const [claim, value] of Object.entries(required)) {
    if (claims[claim] !== value) {
      throw new Error("La licencia offline no corresponde a este usuario, dispositivo o asset.");
    }
  }
  if (
    typeof claims.jti !== "string" || !claims.jti ||
    typeof claims.license_id !== "string" || !claims.license_id
  ) {
    throw new Error("La licencia offline no contiene identificadores válidos.");
  }
  if (!keys.length) throw new Error("No hay una clave pública guardada para validar la licencia.");

  const signingBytes = new TextEncoder().encode(`${segments[0]}.${segments[1]}`);
  const signingInput = new Uint8Array(signingBytes.byteLength);
  signingInput.set(signingBytes);
  const signatureBytes = decodeBase64Url(segments[2]);
  const signature = new Uint8Array(signatureBytes.byteLength);
  signature.set(signatureBytes);
  for (const entry of keys) {
    if (entry.algorithm !== "RS256") continue;
    try {
      const key = await crypto.subtle.importKey(
        "spki",
        pemToDer(entry.public_key),
        { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
        false,
        ["verify"],
      );
      if (await crypto.subtle.verify(
        { name: "RSASSA-PKCS1-v1_5" },
        key,
        signature,
        signingInput,
      )) return;
    } catch {
      // A malformed or unrelated cached key must never make the license valid.
    }
  }
  throw new Error("La firma de la licencia offline no es válida.");
}
