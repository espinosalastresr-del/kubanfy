/** Range download of KBY2 into IndexedDB. Never marks incomplete as ready. */

import { parseHeader } from "./kby2";
import {
  getChunk,
  putChunk,
  putLicense,
  putTrack,
  type OfflineTrackRecord,
} from "./offlineDb";
import type { MusicDownloadResult, OfflineBootstrapItem } from "./api";

export type DownloadProgress = {
  trackId: string;
  completedChunks: number;
  totalChunks: number;
  status: OfflineTrackRecord["status"];
};

async function fetchRange(url: string, start: number, end: number): Promise<Uint8Array> {
  const response = await fetch(url, { headers: { Range: `bytes=${start}-${end}` } });
  if (!(response.status === 206 || response.status === 200)) {
    throw new Error(`Range HTTP ${response.status}`);
  }
  return new Uint8Array(await response.arrayBuffer());
}

/**
 * Download KBY2 asset into IDB as encrypted records.
 * Status becomes `ready` only when every chunk is stored.
 */
export async function downloadKby2ToOffline(opts: {
  trackId: string;
  title: string;
  duration?: number | null;
  quality: string;
  url: string;
  contentHash: string;
  kbyKey: string;
  assetVersion: number;
  offlineLicense: string;
  offlineLicenseExpiresAt: string;
  deviceId: string;
  source: "bootstrap" | "premium";
  artworkUrl?: string | null;
  onProgress?: (p: DownloadProgress) => void;
}): Promise<OfflineTrackRecord> {
  const headBytes = await fetchRange(opts.url, 0, 4095);
  const { header, headerEnd } = parseHeader(headBytes);
  const totalChunks = header.chunk_count;
  const now = Date.now();

  let track: OfflineTrackRecord = {
    trackId: opts.trackId,
    title: opts.title,
    duration: opts.duration ?? null,
    quality: opts.quality,
    contentHash: opts.contentHash,
    assetVersion: opts.assetVersion,
    kbyKey: opts.kbyKey,
    artworkUrl: opts.artworkUrl ?? null,
    source: opts.source,
    status: "partial",
    totalChunks,
    completedChunks: 0,
    totalBytes: header.total_size,
    headerEnd,
    chunkSize: header.chunk_size,
    createdAt: now,
    updatedAt: now,
    lastAccessedAt: now,
  };
  await putTrack(track);

  await putLicense({
    trackId: opts.trackId,
    token: opts.offlineLicense,
    expiresAt: opts.offlineLicenseExpiresAt,
    quality: opts.quality,
    contentHash: opts.contentHash,
    assetVersion: opts.assetVersion,
    deviceId: opts.deviceId,
    source: opts.source,
    updatedAt: now,
  });

  let completed = 0;
  for (let index = 0; index < totalChunks; index++) {
    const existing = await getChunk(opts.trackId, opts.quality, index);
    if (existing?.verified) {
      completed += 1;
      opts.onProgress?.({
        trackId: opts.trackId,
        completedChunks: completed,
        totalChunks,
        status: "partial",
      });
      continue;
    }
    const start = headerEnd + index * header.chunk_size;
    const end = Math.min(start + header.chunk_size, header.total_size) - 1;
    const encrypted = await fetchRange(opts.url, start, end);
    if (encrypted.byteLength < 8) {
      track = { ...track, status: "failed", updatedAt: Date.now() };
      await putTrack(track);
      throw new Error(`Chunk ${index} vacío o corrupto`);
    }
    await putChunk({
      id: `${opts.trackId}:${opts.quality}:${index}`,
      trackId: opts.trackId,
      quality: opts.quality,
      chunkIndex: index,
      encryptedBytes: encrypted.buffer.slice(
        encrypted.byteOffset,
        encrypted.byteOffset + encrypted.byteLength,
      ),
      byteLength: encrypted.byteLength,
      verified: true,
      downloadedAt: Date.now(),
    });
    completed += 1;
    opts.onProgress?.({
      trackId: opts.trackId,
      completedChunks: completed,
      totalChunks,
      status: "partial",
    });
  }

  if (completed !== totalChunks || totalChunks <= 0) {
    track = { ...track, completedChunks: completed, status: "partial", updatedAt: Date.now() };
    await putTrack(track);
    throw new Error("Descarga incompleta: no se marca como disponible offline");
  }

  track = {
    ...track,
    completedChunks: completed,
    status: "ready",
    updatedAt: Date.now(),
  };
  await putTrack(track);
  opts.onProgress?.({
    trackId: opts.trackId,
    completedChunks: completed,
    totalChunks,
    status: "ready",
  });
  return track;
}

export async function materializeBootstrapItem(
  item: OfflineBootstrapItem,
  deviceId: string,
  onProgress?: (p: DownloadProgress) => void,
) {
  return downloadKby2ToOffline({
    trackId: String(item.track_id),
    title: item.title,
    duration: item.duration ?? null,
    quality: item.quality,
    url: item.url,
    contentHash: item.content_hash,
    kbyKey: item.kby_key,
    assetVersion: item.asset_version,
    offlineLicense: item.offline_license,
    offlineLicenseExpiresAt: item.offline_license_expires_at,
    deviceId,
    source: "bootstrap",
    onProgress,
  });
}

export async function materializePremiumDownload(
  trackId: string,
  title: string,
  result: MusicDownloadResult,
  deviceId: string,
  onProgress?: (p: DownloadProgress) => void,
) {
  if (!result.url || !result.kby_key || !result.content_hash || !result.offline_license) {
    throw new Error("La respuesta de descarga no incluye URL/licencia offline completa");
  }
  return downloadKby2ToOffline({
    trackId,
    title,
    quality: result.quality,
    url: result.url,
    contentHash: result.content_hash,
    kbyKey: result.kby_key,
    assetVersion: result.asset_version ?? 1,
    offlineLicense: result.offline_license,
    offlineLicenseExpiresAt: result.offline_license_expires_at || "",
    deviceId,
    source: "premium",
    onProgress,
  });
}

export async function isTrackReadyOffline(trackId: string): Promise<boolean> {
  const { getTrack } = await import("./offlineDb");
  const track = await getTrack(trackId);
  return Boolean(
    track &&
      track.status === "ready" &&
      track.totalChunks > 0 &&
      track.completedChunks === track.totalChunks,
  );
}
