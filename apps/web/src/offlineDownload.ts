/** Resumable, integrity-checked KBY2 downloads into IndexedDB. */

import { chunkRange, decryptChunk, parseHeader } from "./kby2";
import { fetchRange } from "./rangeTransport";
import { cacheOfflineLicensePublicKey } from "./offlineLicense";
import {
  canResumeDownload,
  kby2HeaderEnd,
  validateDownloadHeader,
  verifyEncryptedChunk,
} from "./offlineDownloadCore";
import {
  getChunk,
  getTrack,
  headerBytesToB64,
  putChunk,
  putLicense,
  putTrack,
  removeOfflineTrack,
  type OfflineTrackRecord,
} from "./offlineDb";
import type { MusicDownloadResult, OfflineBootstrapItem } from "./api";

export type DownloadProgress = {
  trackId: string;
  completedChunks: number;
  totalChunks: number;
  status: OfflineTrackRecord["status"];
};

function assertNotAborted(signal: AbortSignal): void {
  if (signal.aborted) {
    throw signal.reason instanceof Error
      ? signal.reason
      : new DOMException("Descarga cancelada", "AbortError");
  }
}

/**
 * Download KBY2 encrypted records into IndexedDB.
 *
 * Existing chunks are reused only when the immutable asset identity matches
 * and AES-GCM authentication succeeds again. Progress is committed after
 * every chunk so a later invocation can safely resume.
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
  signal?: AbortSignal;
}): Promise<OfflineTrackRecord> {
  const signal = opts.signal ?? new AbortController().signal;
  if (!opts.trackId || !opts.deviceId || !opts.kbyKey || !opts.offlineLicense) {
    throw new Error("La autorización offline está incompleta.");
  }
  const licenseExpiry = Date.parse(opts.offlineLicenseExpiresAt);
  if (!Number.isFinite(licenseExpiry) || licenseExpiry <= Date.now()) {
    throw new Error("La licencia offline está ausente o vencida.");
  }

  assertNotAborted(signal);
  // Cache the verification key online before storing a license for later offline use.
  await cacheOfflineLicensePublicKey();
  assertNotAborted(signal);
  // Read the fixed 9-byte prefix first, then fetch exactly the declared header.
  // A fixed 8 KiB request can legitimately be clamped by the server for very
  // short assets, which strict Range validation must not mistake for corruption.
  const prefix = await fetchRange(opts.url, 0, 8, signal);
  assertNotAborted(signal);
  const headerEndExpected = kby2HeaderEnd(prefix);
  const headBytes = await fetchRange(opts.url, 0, headerEndExpected - 1, signal);
  assertNotAborted(signal);
  const { header, headerEnd } = parseHeader(headBytes);
  if (headerEnd !== headerEndExpected) {
    throw new Error("El límite del header KBY2 cambió durante la descarga.");
  }
  validateDownloadHeader(header, opts.contentHash, opts.quality);
  const headerJsonBytes = headBytes.slice(9, headerEnd);
  const headerBytesB64 = headerBytesToB64(headerJsonBytes);
  const totalChunks = header.chunk_count;

  const normalRecord = 4 + 12 + header.chunk_size + 16;
  const lastPlain =
    header.plaintext_size - header.chunk_size * Math.max(0, totalChunks - 1);
  const lastRecord = 4 + 12 + lastPlain + 16;
  const totalEncrypted =
    headerEnd + normalRecord * Math.max(0, totalChunks - 1) + lastRecord;

  const existingTrack = await getTrack(opts.trackId);
  const expectedIdentity = {
    contentHash: opts.contentHash,
    assetVersion: opts.assetVersion,
    quality: opts.quality,
    totalChunks,
    headerEnd,
    chunkSize: header.chunk_size,
    headerBytesB64,
  };
  const resume = canResumeDownload(existingTrack, expectedIdentity);
  if (existingTrack && !resume) {
    // A track ID can point to a new immutable generation. Never mix its chunks
    // with a previous hash, version, quality or KBY2 header.
    await removeOfflineTrack(opts.trackId);
  }

  const now = Date.now();
  let track: OfflineTrackRecord = {
    trackId: opts.trackId,
    title: opts.title,
    duration: opts.duration ?? null,
    quality: opts.quality,
    contentHash: opts.contentHash,
    assetVersion: opts.assetVersion,
    kbyKey: opts.kbyKey,
    headerBytesB64,
    artworkUrl: opts.artworkUrl ?? null,
    source: opts.source,
    status: "partial",
    totalChunks,
    completedChunks: 0,
    totalBytes: totalEncrypted,
    headerEnd,
    chunkSize: header.chunk_size,
    createdAt: resume ? existingTrack!.createdAt : now,
    updatedAt: now,
    lastAccessedAt: resume ? existingTrack!.lastAccessedAt : now,
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
  try {
    for (let index = 0; index < totalChunks; index += 1) {
      assertNotAborted(signal);
      const existing = await getChunk(opts.trackId, opts.quality, index);
      let chunkVerified = false;

      if (existing?.verified && existing.byteLength === existing.encryptedBytes.byteLength) {
        try {
          await verifyEncryptedChunk(
            new Uint8Array(existing.encryptedBytes),
            header,
            index,
            (record, chunkIndex) =>
              decryptChunk(record, headerJsonBytes, chunkIndex, opts.kbyKey),
          );
          chunkVerified = true;
        } catch {
          // A stale/corrupt local chunk is replaced from the authorized source.
        }
      }

      if (!chunkVerified) {
        const { start, end } = chunkRange(header, headerEnd, index);
        const encrypted = await fetchRange(opts.url, start, end, signal);
        assertNotAborted(signal);
        await verifyEncryptedChunk(
          encrypted,
          header,
          index,
          (record, chunkIndex) =>
            decryptChunk(record, headerJsonBytes, chunkIndex, opts.kbyKey),
        );

        const encryptedCopy = new Uint8Array(encrypted.byteLength);
        encryptedCopy.set(encrypted);
        await putChunk({
          id: `${opts.trackId}:${opts.quality}:${index}`,
          trackId: opts.trackId,
          quality: opts.quality,
          chunkIndex: index,
          encryptedBytes: encryptedCopy.buffer,
          byteLength: encrypted.byteLength,
          verified: true,
          downloadedAt: Date.now(),
        });
      }

      completed += 1;
      track = {
        ...track,
        completedChunks: completed,
        updatedAt: Date.now(),
        lastAccessedAt: Date.now(),
      };
      await putTrack(track);
      opts.onProgress?.({
        trackId: opts.trackId,
        completedChunks: completed,
        totalChunks,
        status: "partial",
      });
    }
  } catch (error) {
    track = {
      ...track,
      completedChunks: completed,
      status: "partial",
      updatedAt: Date.now(),
    };
    await putTrack(track).catch(() => {});
    throw error;
  }

  assertNotAborted(signal);
  if (licenseExpiry <= Date.now()) {
    track = { ...track, completedChunks: completed, status: "partial", updatedAt: Date.now() };
    await putTrack(track);
    throw new Error("La licencia offline venció durante la descarga. Reanuda para renovarla.");
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
  signal?: AbortSignal,
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
    signal,
  });
}

export async function materializePremiumDownload(
  trackId: string,
  title: string,
  result: MusicDownloadResult,
  deviceId: string,
  onProgress?: (p: DownloadProgress) => void,
  signal?: AbortSignal,
) {
  if (
    !result.url ||
    !result.kby_key ||
    !result.content_hash ||
    !result.offline_license ||
    !result.offline_license_expires_at
  ) {
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
    offlineLicenseExpiresAt: result.offline_license_expires_at,
    deviceId,
    source: "premium",
    onProgress,
    signal,
  });
}

export async function isTrackReadyOffline(trackId: string): Promise<boolean> {
  const track = await getTrack(trackId);
  return Boolean(
    track &&
      track.status === "ready" &&
      track.totalChunks > 0 &&
      track.completedChunks === track.totalChunks &&
      track.headerBytesB64,
  );
}
