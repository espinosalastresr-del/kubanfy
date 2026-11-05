/** Offline KBY2 MSE helpers — load encrypted chunks from IndexedDB. */

import { decryptChunk, parseHeader, parseTopLevelBoxes, type KbyHeader } from "./kby2";
import { getChunk, getTrack, type OfflineTrackRecord } from "./offlineDb";
import { isTrackReadyOffline } from "./offlineDownload";

export { isTrackReadyOffline };

export function headerBytesFromB64(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export async function loadOfflineTrackMeta(trackId: string): Promise<{
  track: OfflineTrackRecord;
  header: KbyHeader;
  headerBytes: Uint8Array;
  key: string;
}> {
  const track = await getTrack(trackId);
  if (
    !track ||
    track.status !== "ready" ||
    track.completedChunks !== track.totalChunks ||
    track.totalChunks <= 0 ||
    !track.headerBytesB64
  ) {
    throw new Error("Track no disponible offline (incompleto o sin header)");
  }
  const headerBytes = headerBytesFromB64(track.headerBytesB64);
  // Reconstruct a synthetic header buffer for parseHeader: MAGIC+VERSION+LEN+JSON
  const json = headerBytes;
  const len = json.length;
  const buf = new Uint8Array(9 + len);
  buf[0] = 0x4b; buf[1] = 0x42; buf[2] = 0x59; buf[3] = 0x32; // KBY2
  buf[4] = 2;
  new DataView(buf.buffer).setUint32(5, len);
  buf.set(json, 9);
  const { header } = parseHeader(buf);
  return { track, header, headerBytes, key: track.kbyKey };
}

export async function readOfflineChunk(
  trackId: string,
  quality: string,
  index: number,
): Promise<Uint8Array> {
  const rec = await getChunk(trackId, quality, index);
  if (!rec?.encryptedBytes) {
    throw new Error(`Chunk offline ${index} no encontrado`);
  }
  return new Uint8Array(rec.encryptedBytes);
}

export async function decryptOfflineChunk(
  encrypted: Uint8Array,
  headerBytes: Uint8Array,
  index: number,
  key: string,
): Promise<Uint8Array> {
  return decryptChunk(encrypted, headerBytes, index, key);
}

export { parseTopLevelBoxes };
