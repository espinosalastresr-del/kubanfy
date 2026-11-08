import { createDeviceChallenge, getDeviceId, listDevices, verifyDeviceChallenge } from "./api";

const DB_NAME = "kubanfy-secure-identity";
const STORE_NAME = "keys";
const DB_VERSION = 1;

type BrowserIdentity = {
  privateKey: CryptoKey;
  publicKey: string;
};

let enrollmentInFlight: Promise<"verified" | "unsupported" | "recovery-required"> | null = null;

function openKeyDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("El almacenamiento seguro del navegador no está disponible."));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) db.createObjectStore(STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("No se pudo abrir el almacén seguro."));
    request.onblocked = () => reject(new Error("El almacén seguro está bloqueado por otra pestaña."));
  });
}

async function readIdentity(deviceId: string): Promise<BrowserIdentity | null> {
  const db = await openKeyDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).get(deviceId);
      request.onsuccess = () => {
        const value = request.result as BrowserIdentity | undefined;
        if (
          value?.privateKey?.type === "private" &&
          value.privateKey.algorithm.name === "Ed25519" &&
          typeof value.publicKey === "string"
        ) {
          resolve(value);
        } else {
          resolve(null);
        }
      };
      request.onerror = () => reject(request.error || new Error("No se pudo leer la identidad del navegador."));
    });
  } finally {
    db.close();
  }
}

async function writeIdentity(deviceId: string, identity: BrowserIdentity): Promise<void> {
  const db = await openKeyDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      transaction.objectStore(STORE_NAME).put(identity, deviceId);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error || new Error("No se pudo guardar la identidad del navegador."));
      transaction.onabort = () => reject(transaction.error || new Error("Se canceló el guardado de la identidad."));
    });
  } finally {
    db.close();
  }
}

function toBase64(bytes: ArrayBuffer): string {
  const view = new Uint8Array(bytes);
  let binary = "";
  for (let offset = 0; offset < view.length; offset += 0x8000) {
    binary += String.fromCharCode(...view.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

async function createIdentity(): Promise<BrowserIdentity> {
  // The private key is generated non-extractable. Only the public key can be exported.
  const pair = await crypto.subtle.generateKey(
    { name: "Ed25519" } as Algorithm,
    false,
    ["sign", "verify"],
  ) as CryptoKeyPair;
  const publicKey = toBase64(await crypto.subtle.exportKey("raw", pair.publicKey));
  return { privateKey: pair.privateKey, publicKey };
}

async function signMessage(privateKey: CryptoKey, message: string): Promise<string> {
  const signature = await crypto.subtle.sign(
    { name: "Ed25519" } as Algorithm,
    privateKey,
    new TextEncoder().encode(message),
  );
  return toBase64(signature);
}

export async function enrollCurrentBrowserIdentity(): Promise<"verified" | "unsupported" | "recovery-required"> {
  if (enrollmentInFlight) return enrollmentInFlight;
  enrollmentInFlight = (async () => {
    if (!window.isSecureContext || !globalThis.crypto?.subtle || typeof indexedDB === "undefined") {
      return "unsupported" as const;
    }

    const devices = await listDevices();
    const device = devices.find((item) => item.device_id === getDeviceId() && item.status === "active");
    if (!device) throw new Error("No se encontró el navegador activo en la lista de dispositivos.");

    let identity = await readIdentity(device.device_id);
    if (device.identity_verified && !identity) return "recovery-required" as const;

    if (!identity) {
      identity = await createIdentity();
      // Store private CryptoKey and public half atomically before requesting a challenge.
      await writeIdentity(device.device_id, identity);
    }

    const challenge = await createDeviceChallenge(device.id, identity.publicKey);
    const signature = await signMessage(identity.privateKey, challenge.message);
    await verifyDeviceChallenge(challenge.challenge_id, signature);
    return "verified" as const;
  })();

  try {
    return await enrollmentInFlight;
  } catch (error) {
    if (error instanceof Error && error.name === "NotSupportedError") return "unsupported";
    throw error;
  } finally {
    enrollmentInFlight = null;
  }
}
