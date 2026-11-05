/** IndexedDB `kubanfy-offline` — metadata, encrypted chunks, licenses, download state. */

const DB_NAME = "kubanfy-offline";
const DB_VERSION = 1;

export type OfflineTrackRecord = {
  trackId: string;
  title: string;
  duration: number | null;
  quality: string;
  contentHash: string;
  assetVersion: number;
  kbyKey: string;
  /** Base64 of KBY2 JSON header bytes (after MAGIC+VERSION+LEN). Required for offline decrypt AAD. */
  headerBytesB64?: string;
  artworkUrl?: string | null;
  source: "bootstrap" | "premium" | "auto";
  status: "partial" | "ready" | "failed";
  totalChunks: number;
  completedChunks: number;
  totalBytes: number;
  headerEnd: number;
  chunkSize: number;
  createdAt: number;
  updatedAt: number;
  lastAccessedAt: number;
};

export type OfflineChunkRecord = {
  id: string;
  trackId: string;
  quality: string;
  chunkIndex: number;
  encryptedBytes: ArrayBuffer;
  byteLength: number;
  verified: boolean;
  downloadedAt: number;
};

export type OfflineLicenseRecord = {
  trackId: string;
  token: string;
  expiresAt: string;
  quality: string;
  contentHash: string;
  assetVersion: number;
  deviceId: string;
  source: "bootstrap" | "premium" | "auto";
  updatedAt: number;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error || new Error("IndexedDB open failed"));
    req.onsuccess = () => resolve(req.result);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("tracks")) {
        db.createObjectStore("tracks", { keyPath: "trackId" });
      }
      if (!db.objectStoreNames.contains("chunks")) {
        const chunks = db.createObjectStore("chunks", { keyPath: "id" });
        chunks.createIndex("byTrack", "trackId", { unique: false });
      }
      if (!db.objectStoreNames.contains("licenses")) {
        db.createObjectStore("licenses", { keyPath: "trackId" });
      }
    };
  });
}

function txDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error || new Error("IndexedDB tx failed"));
    tx.onabort = () => reject(tx.error || new Error("IndexedDB tx aborted"));
  });
}

export async function putTrack(record: OfflineTrackRecord): Promise<void> {
  const db = await openDb();
  const tx = db.transaction("tracks", "readwrite");
  tx.objectStore("tracks").put(record);
  await txDone(tx);
}

export async function getTrack(trackId: string): Promise<OfflineTrackRecord | undefined> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("tracks", "readonly");
    const req = tx.objectStore("tracks").get(trackId);
    req.onsuccess = () => resolve(req.result as OfflineTrackRecord | undefined);
    req.onerror = () => reject(req.error);
  });
}

export async function listTracks(): Promise<OfflineTrackRecord[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("tracks", "readonly");
    const req = tx.objectStore("tracks").getAll();
    req.onsuccess = () => resolve((req.result as OfflineTrackRecord[]) || []);
    req.onerror = () => reject(req.error);
  });
}

/** Only tracks that are fully downloaded. Incomplete never appears here. */
export async function listReadyTracks(): Promise<OfflineTrackRecord[]> {
  const all = await listTracks();
  return all.filter(
    (t) =>
      t.status === "ready" &&
      t.totalChunks > 0 &&
      t.completedChunks === t.totalChunks &&
      Boolean(t.headerBytesB64),
  );
}

export async function putChunk(record: OfflineChunkRecord): Promise<void> {
  const db = await openDb();
  const tx = db.transaction("chunks", "readwrite");
  tx.objectStore("chunks").put(record);
  await txDone(tx);
}

export async function getChunk(
  trackId: string,
  quality: string,
  chunkIndex: number,
): Promise<OfflineChunkRecord | undefined> {
  const db = await openDb();
  const id = `${trackId}:${quality}:${chunkIndex}`;
  return new Promise((resolve, reject) => {
    const tx = db.transaction("chunks", "readonly");
    const req = tx.objectStore("chunks").get(id);
    req.onsuccess = () => resolve(req.result as OfflineChunkRecord | undefined);
    req.onerror = () => reject(req.error);
  });
}

export async function countChunks(trackId: string): Promise<number> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("chunks", "readonly");
    const idx = tx.objectStore("chunks").index("byTrack");
    const req = idx.count(IDBKeyRange.only(trackId));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function putLicense(record: OfflineLicenseRecord): Promise<void> {
  const db = await openDb();
  const tx = db.transaction("licenses", "readwrite");
  tx.objectStore("licenses").put(record);
  await txDone(tx);
}

export async function getLicense(trackId: string): Promise<OfflineLicenseRecord | undefined> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("licenses", "readonly");
    const req = tx.objectStore("licenses").get(trackId);
    req.onsuccess = () => resolve(req.result as OfflineLicenseRecord | undefined);
    req.onerror = () => reject(req.error);
  });
}

export async function touchTrackAccess(trackId: string): Promise<void> {
  const track = await getTrack(trackId);
  if (!track) return;
  await putTrack({ ...track, lastAccessedAt: Date.now() });
}

export async function removeOfflineTrack(trackId: string): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(["tracks", "chunks", "licenses"], "readwrite");
  tx.objectStore("tracks").delete(trackId);
  tx.objectStore("licenses").delete(trackId);
  const idx = tx.objectStore("chunks").index("byTrack");
  const req = idx.openCursor(IDBKeyRange.only(trackId));
  req.onsuccess = () => {
    const cursor = req.result;
    if (cursor) {
      cursor.delete();
      cursor.continue();
    }
  };
  await txDone(tx);
}

export function headerBytesFromB64(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function headerBytesToB64(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}
