import { getDeviceId } from "./api";

export type OfflineTrack = {
  id: string;
  trackId: string;
  title: string;
  quality: "low" | "medium";
  blob: Blob;
  kbyKey: string;
  contentHash: string;
  assetVersion: number;
  licenseToken: string;
  publicKey: string;
  expiresAt: string;
  deviceId: string;
  sizeBytes: number;
  savedAt: number;
};

const DB_NAME = "kubanfy-offline";
const STORE_NAME = "tracks";
const DB_VERSION = 1;
const RANGE_BYTES = 1024 * 1024;
const RETRYABLE = new Set([408, 425, 429, 500, 502, 503, 504]);

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("No se pudo abrir el almacenamiento offline"));
  });
}

async function transact<T>(mode: IDBTransactionMode, operation: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, mode);
      const request = operation(tx.objectStore(STORE_NAME));
      let result: T;
      request.onsuccess = () => { result = request.result; };
      request.onerror = () => reject(request.error || new Error("Error del almacenamiento offline"));
      tx.oncomplete = () => resolve(result!);
      tx.onerror = () => reject(tx.error || new Error("Error del almacenamiento offline"));
      tx.onabort = () => reject(tx.error || new Error("Se canceló el almacenamiento offline"));
    });
  } finally {
    db.close();
  }
}

export async function listOfflineTracks(): Promise<OfflineTrack[]> {
  const tracks = await transact<OfflineTrack[]>("readonly", store => store.getAll());
  return tracks.sort((a, b) => b.savedAt - a.savedAt);
}

export async function saveOfflineTrack(track: OfflineTrack): Promise<void> {
  await transact<IDBValidKey>("readwrite", store => store.put(track));
}

export async function deleteOfflineTrack(id: string): Promise<void> {
  await transact<undefined>("readwrite", store => store.delete(id));
}

function decodeBase64Url(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return Uint8Array.from(atob(padded), character => character.charCodeAt(0));
}

function decodeJwtPart(value: string): Record<string, unknown> {
  return JSON.parse(new TextDecoder().decode(decodeBase64Url(value))) as Record<string, unknown>;
}

export async function verifyOfflineLicense(track: OfflineTrack, userId: string): Promise<void> {
  if (track.deviceId !== getDeviceId()) throw new Error("Esta descarga pertenece a otro dispositivo.");
  const parts = track.licenseToken.split(".");
  if (parts.length !== 3) throw new Error("La licencia offline no es válida.");

  const header = decodeJwtPart(parts[0]);
  const claims = decodeJwtPart(parts[1]);
  if (header.alg !== "RS256" || claims.type !== "offline_license") {
    throw new Error("El formato de la licencia offline no es compatible.");
  }

  if (typeof claims.exp !== "number" || claims.exp <= Math.floor(Date.now() / 1000)) {
    throw new Error("La licencia offline ha caducado. Conéctate para renovarla.");
  }
  if (
    claims.sub !== userId ||
    claims.device_id !== track.deviceId ||
    claims.track_id !== track.trackId ||
    claims.quality !== track.quality ||
    claims.asset_version !== track.assetVersion ||
    claims.content_hash !== track.contentHash
  ) {
    throw new Error("La licencia offline no coincide con esta cuenta, dispositivo o archivo.");
  }

  const pem = track.publicKey.replace(/-----BEGIN PUBLIC KEY-----|-----END PUBLIC KEY-----|\s/g, "");
  const keyBytes = Uint8Array.from(atob(pem), character => character.charCodeAt(0));
  const publicKey = await crypto.subtle.importKey(
    "spki", keyBytes, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"],
  );
  const signature = decodeBase64Url(parts[2]);
  const signedContent = new TextEncoder().encode(parts[0] + "." + parts[1]);
  const valid = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", publicKey, signature.slice().buffer as ArrayBuffer, signedContent);
  if (!valid) throw new Error("La firma de la licencia offline no es válida.");
}

async function fetchRange(url: string, start: number, end: number, total: number): Promise<Uint8Array> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    try {
      const response = await fetch(url, { headers: { Range: `bytes=${start}-${end}` } });
      if (RETRYABLE.has(response.status) && attempt < 3) {
        lastError = new Error(`HTTP ${response.status}`);
      } else {
        if (response.status !== 206) throw new Error(`El servidor no permitió reanudar la descarga (HTTP ${response.status}).`);
        const match = response.headers.get("Content-Range")?.match(/^bytes (\d+)-(\d+)\/(\d+)$/);
        if (!match || Number(match[1]) !== start || Number(match[2]) !== end || Number(match[3]) !== total) {
          throw new Error("El servidor devolvió un rango de descarga incoherente.");
        }
        const bytes = new Uint8Array(await response.arrayBuffer());
        if (bytes.length !== end - start + 1) throw new Error("La descarga llegó incompleta.");
        return bytes;
      }
    } catch (error) {
      lastError = error;
      if (attempt === 3 || !(error instanceof TypeError || (error instanceof Error && /HTTP (408|425|429|500|502|503|504)|fetch|network|load failed/i.test(error.message)))) {
        throw error;
      }
    }
    await new Promise(resolve => window.setTimeout(resolve, [400, 900, 1800][attempt]));
  }
  throw lastError instanceof Error ? lastError : new Error("No se pudo descargar el audio.");
}

export async function downloadProtectedAudio(
  url: string,
  totalBytes: number,
  onProgress?: (received: number, total: number) => void,
): Promise<Blob> {
  if (!Number.isSafeInteger(totalBytes) || totalBytes <= 0) {
    throw new Error("El servidor no informó un tamaño de descarga válido.");
  }
  const chunks: Uint8Array[] = [];
  let received = 0;
  for (let start = 0; start < totalBytes; start += RANGE_BYTES) {
    const end = Math.min(totalBytes - 1, start + RANGE_BYTES - 1);
    const chunk = await fetchRange(url, start, end, totalBytes);
    chunks.push(chunk);
    received += chunk.length;
    onProgress?.(received, totalBytes);
  }
  if (received !== totalBytes) throw new Error("La descarga no superó la comprobación de tamaño.");
  return new Blob(chunks.map(chunk => chunk.slice().buffer as ArrayBuffer), { type: "application/octet-stream" });
}
