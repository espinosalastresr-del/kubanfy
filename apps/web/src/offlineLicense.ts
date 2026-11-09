import { getOfflineLicensePublicKey } from "./api";
import {
  verifyOfflineLicenseToken,
  type OfflineLicenseExpectations,
  type OfflineLicenseVerificationKey,
} from "./offlineLicenseCore";

const KEY_CACHE = "kubanfy.offline.public-keys.v1";
const MAX_CACHED_KEYS = 5;

type CachedPublicKey = OfflineLicenseVerificationKey & { fetched_at: number };

function readCachedKeys(): CachedPublicKey[] {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(KEY_CACHE) || "[]");
    return Array.isArray(parsed)
      ? parsed.filter((entry) =>
          entry?.algorithm === "RS256" &&
          typeof entry.key_id === "string" &&
          typeof entry.public_key === "string",
        )
      : [];
  } catch {
    return [];
  }
}

function pemToDer(pem: string): ArrayBuffer {
  const body = pem
    .replace(/-----BEGIN PUBLIC KEY-----/g, "")
    .replace(/-----END PUBLIC KEY-----/g, "")
    .replace(/\s+/g, "");
  if (!body || body.length > 8192) throw new Error("Clave pública offline inválida.");
  const binary = atob(body);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes.buffer;
}

export async function cacheOfflineLicensePublicKey(): Promise<void> {
  const response = await getOfflineLicensePublicKey();
  if (
    response.algorithm !== "RS256" ||
    !/^[a-f0-9]{16}$/i.test(response.key_id) ||
    !response.public_key.includes("BEGIN PUBLIC KEY")
  ) {
    throw new Error("La API devolvió una clave pública offline inválida.");
  }

  const fingerprint = new Uint8Array(
    await crypto.subtle.digest("SHA-256", new TextEncoder().encode(response.public_key)),
  );
  const expectedId = Array.from(fingerprint.slice(0, 8), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  if (expectedId.toLowerCase() !== response.key_id.toLowerCase()) {
    throw new Error("La huella de la clave pública offline no coincide.");
  }

  await crypto.subtle.importKey(
    "spki",
    pemToDer(response.public_key),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );

  const next: CachedPublicKey = {
    algorithm: "RS256",
    key_id: response.key_id,
    public_key: response.public_key,
    fetched_at: Date.now(),
  };
  const keys = [next, ...readCachedKeys().filter((key) => key.key_id !== next.key_id)]
    .slice(0, MAX_CACHED_KEYS);
  try {
    window.localStorage.setItem(KEY_CACHE, JSON.stringify(keys));
  } catch {
    throw new Error("No se pudo guardar la clave pública para validar licencias sin conexión.");
  }
}

export async function verifyOfflineLicense(
  token: string,
  expected: OfflineLicenseExpectations,
): Promise<void> {
  const keys = readCachedKeys();
  if (!keys.length) {
    throw new Error("No hay una clave pública guardada. Conéctate una vez para verificar esta licencia.");
  }
  await verifyOfflineLicenseToken(token, expected, keys);
}
