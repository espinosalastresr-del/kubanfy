import { createDeviceChallenge, getDeviceId, listDevices, verifyDeviceChallenge } from "./api";

const DB_NAME = "kubanfy-secure-identity";
const STORE_NAME = "keys";
const DB_VERSION = 1;

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

async function readPrivateKey(deviceId: string): Promise<CryptoKey | null> {
  const db = await openKeyDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).get(deviceId);
      request.onsuccess = () => {
        const key = request.result as CryptoKey | undefined;
        resolve(key && key.type === "private" && key.algorithm.name === "Ed25519" ? key : null);
      };
      request.onerror = () => reject(request.error || new Error("No se pudo leer la identidad del navegador."));
    });
  } finally {
    db.close();
  }
}

async function writePrivateKey(deviceId: string, key: CryptoKey): Promise<void> {
  const db = await openKeyDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      transaction.objectStore(STORE_NAME).put(key, deviceId);
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

async function createNonExtractableIdentity(): Promise<{ privateKey: CryptoKey; publicKey: string }> {
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

    let devices;
    try {
      devices = await listDevices();
    } catch (error) {
      throw error;
    }
    const device = devices.find((item) => item.device_id === getDeviceId() && item.status === "active");
    if (!device) throw new Error("No se encontró el navegador activo en la lista de dispositivos.");

    let privateKey = await readPrivateKey(device.device_id);
    if (device.identity_verified && !privateKey) return "recovery-required" as const;

    if (!privateKey) {
      const identity = await createNonExtractableIdentity();
      privateKey = identity.privateKey;
      await writePrivateKey(device.device_id, privateKey);
      const challenge = await createDeviceChallenge(device.id, identity.publicKey);
      const signature = await signMessage(privateKey, challenge.message);
      await verifyDeviceChallenge(challenge.challenge_id, signature);
      return "verified" as const;
    }

    // Re-prove possession when this browser starts a new authenticated session.
    // The server binds each short-lived challenge to this user, device and public key.
    const publicKey = await getStoredPublicKey(device.device_id, privateKey);
    const challenge = await createDeviceChallenge(device.id, publicKey);
    const signature = await signMessage(privateKey, challenge.message);
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

async function getStoredPublicKey(deviceId: string, privateKey: CryptoKey): Promise<string> {
  // The public half is intentionally stored separately; private CryptoKey remains non-extractable.
  const db = await openKeyDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readonly");
      const request = tx.objectStore(STORE_NAME).get(`${deviceId}:public`);
      request.onsuccess = () => {
        if (typeof request.result === "string") {
          resolve(request.result);
          return;
        }
        // Existing installs from the first enrollment version can recover the public key
        // from a companion public-key record written during enrollment.
        reject(new Error("No se encontró la clave pública asociada a este navegador."));
      };
      request.onerror = () => reject(request.error || new Error("No se pudo leer la clave pública."));
    });
  } finally {
    db.close();
  }
}
