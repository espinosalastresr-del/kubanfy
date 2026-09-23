/**
 * Durable offline download queue.
 *
 * Network failures never discard the completed prefix:
 *   final audio ← atomic rename ← .part
 *
 * A fresh signed URL is requested for every retry because delivery URLs
 * are intentionally short-lived. Resume uses HTTP Range against that URL.
 */

import {apiRequest, getDeviceId, getOfflineUserId} from '../api/client';
import {encryptOfflineFile} from './offlineCrypto';
import {verifyOfflineLicense} from './offlineLicenseVerifier';
import {
  listDownloadJobs,
  saveDownloadJobs,
  upsertOfflineTrack,
} from './storage';
import {AudioQuality, DownloadJob, OfflineTrackMeta} from './types';

type DownloadResponse = {
  url?: string;
  signed_url?: string;
  track_id?: string;
  quality?: string;
  content_hash?: string;
  size_bytes?: number;
  offline_license?: string;
  offline_license_expires_at?: string;
};

const MAX_ATTEMPTS = 4;
const RETRY_DELAYS_MS = [1500, 4000, 10000, 20000];
const COPY_CHUNK_BYTES = 1024 * 1024;

let queueRunning = false;

function jobId(trackId: string, quality: AudioQuality): string {
  return `${trackId}:${quality}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function fileUri(path: string): string {
  return path.startsWith('file://') ? path : `file://${path}`;
}

async function loadRNFS(): Promise<any> {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  return require('react-native-fs');
}

async function ensureDir(RNFS: any, dir: string): Promise<void> {
  if (!(await RNFS.exists(dir))) {
    await RNFS.mkdir(dir);
  }
}

async function cleanupInterruptedKfyArtifacts(RNFS: any, dir: string): Promise<void> {
  try {
    if (!(await RNFS.exists(dir))) return;
    const entries = await RNFS.readDir(dir);
    await Promise.all(
      entries
        .filter((entry: {name: string}) =>
          entry.name.endsWith('.kfy.part') || entry.name.endsWith('.meta.part'),
        )
        .map((entry: {path: string}) => RNFS.unlink(entry.path).catch(() => undefined)),
    );
  } catch {
    // Best-effort cleanup; resumable source .audio.part files are preserved.
  }
}

async function appendFileInChunks(
  RNFS: any,
  source: string,
  destination: string,
): Promise<void> {
  let position = 0;
  const stat = await RNFS.stat(source);
  const sourceSize = Number(stat.size);

  while (position < sourceSize) {
    const length = Math.min(COPY_CHUNK_BYTES, sourceSize - position);
    const base64 = await RNFS.read(source, length, position, 'base64');
    await RNFS.appendFile(destination, base64, 'base64');
    position += length;
  }
}

async function sha256(RNFS: any, path: string): Promise<string | null> {
  try {
    if (typeof RNFS.hash !== 'function') {
      return null;
    }
    return await RNFS.hash(path, 'sha256');
  } catch {
    return null;
  }
}

async function updateProgress(
  id: string,
  bytes: number,
  total: number | undefined,
): Promise<void> {
  const progress = total && total > 0 ? Math.min(0.99, bytes / total) : 0;
  await updateJob(id, {
    bytesDownloaded: bytes,
    totalBytes: total,
    progress: progress > 0 ? progress : 0.05,
  });
}

async function downloadWithResume(
  job: DownloadJob,
): Promise<{
  path: string;
  contentHash?: string;
  sizeBytes: number;
  offlineLicense?: string;
  offlineLicenseExpiresAt?: string;
}> {
  const RNFS = await loadRNFS();
  const dir = `${RNFS.DocumentDirectoryPath}/kubanfy/offline`;
  await ensureDir(RNFS, dir);

  const part = job.tempPath || `${dir}/${job.trackId}_${job.quality}.audio.part`;
  const final = job.finalPath || `${dir}/${job.trackId}_${job.quality}.kfy`;
  const metadata = `${final}.meta`;
  await updateJob(job.id, {tempPath: part, finalPath: final});

  if (await RNFS.exists(final)) {
    const stat = await RNFS.stat(final);
    const size = Number(stat.size);
    if (job.totalBytes && size !== job.totalBytes) {
      await RNFS.unlink(final).catch(() => {});
    } else if (job.contentHash && job.offlineLicense) {
      try {
        const envelope = JSON.parse(await RNFS.readFile(metadata, 'utf8')) as {
          format?: string;
          contentHash?: string;
          plaintextSize?: number;
        };
        if (
          envelope.format !== 'kubanfy-kfy-aes256gcm-v1' ||
          envelope.contentHash !== job.contentHash ||
          !Number.isFinite(Number(envelope.plaintextSize))
        ) {
          throw new Error('Offline metadata mismatch');
        }
        const deviceId = await getDeviceId();
        const userId = await getOfflineUserId();
        if (!userId) throw new Error('Offline license account binding unavailable');
        verifyOfflineLicense(job.offlineLicense, {
          trackId: job.trackId,
          quality: job.quality,
          deviceId,
          userId,
          contentHash: job.contentHash,
        });
        return {
          path: final,
          contentHash: job.contentHash,
          sizeBytes: size,
          offlineLicense: job.offlineLicense,
          offlineLicenseExpiresAt: job.offlineLicenseExpiresAt,
        };
      } catch {
        await RNFS.unlink(final).catch(() => {});
        await RNFS.unlink(metadata).catch(() => {});
      }
    } else {
      await RNFS.unlink(final).catch(() => {});
      await RNFS.unlink(metadata).catch(() => {});
    }
  }

  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
    try {
      const res = await apiRequest<DownloadResponse>('/v1/music/download', {
        method: 'POST',
        body: JSON.stringify({
          track_id: job.trackId,
          quality: job.quality,
        }),
      });
      const url = res.url || res.signed_url;
      if (!url) {
        throw new Error('No signed URL from server');
      }

      const total = res.size_bytes;
      const expectedHash = res.content_hash;
      if (!expectedHash || !res.offline_license) {
        throw new Error('Offline download requires content hash and license');
      }
      let offset = 0;
      if (await RNFS.exists(part)) {
        offset = Number((await RNFS.stat(part)).size);
      }

      if (total !== undefined && offset > total) {
        await RNFS.unlink(part).catch(() => {});
        offset = 0;
      }

      await updateJob(job.id, {
        bytesDownloaded: offset,
        totalBytes: total,
        contentHash: expectedHash,
        tempPath: part,
        finalPath: final,
        progress: total ? offset / total : 0.05,
        offlineLicense: res.offline_license,
        offlineLicenseExpiresAt: res.offline_license_expires_at,
      });

      const chunk = `${part}.download`;
      await RNFS.unlink(chunk).catch(() => {});

      const headers: Record<string, string> = {};
      if (offset > 0) {
        headers.Range = `bytes=${offset}-`;
      }

      let lastProgressAt = 0;
      const result = await RNFS.downloadFile({
        fromUrl: url,
        toFile: chunk,
        headers,
        background: true,
        discretionary: false,
        progressDivider: 0,
        begin: () => {},
        progress: (p: {bytesWritten: number; contentLength: number}) => {
          const now = Date.now();
          if (now - lastProgressAt < 2000) {
            return;
          }
          lastProgressAt = now;
          const written = Number(p.bytesWritten) || 0;
          const denominator =
            total || (Number(p.contentLength) > 0 ? offset + Number(p.contentLength) : 0);
          void updateProgress(job.id, offset + written, denominator || undefined);
        },
      }).promise;

      const status = Number(result.statusCode || 0);
      if (status >= 400) {
        await RNFS.unlink(chunk).catch(() => {});
        if (status === 416) {
          await RNFS.unlink(part).catch(() => {});
          continue;
        }
        throw new Error(`download HTTP ${status}`);
      }

      const chunkSize = Number((await RNFS.stat(chunk)).size);

      if (offset > 0 && status === 206) {
        if (total !== undefined && offset + chunkSize !== total) {
          await RNFS.unlink(chunk).catch(() => {});
          throw new Error(
            `incomplete range: received ${offset + chunkSize} of ${total} bytes`,
          );
        }
        await appendFileInChunks(RNFS, chunk, part);
        await RNFS.unlink(chunk).catch(() => {});
      } else if (offset > 0 && status === 200) {
        // The server ignored Range. Never append a full response to a prefix.
        await RNFS.unlink(part).catch(() => {});
        await RNFS.moveFile(chunk, part);
      } else {
        // Initial request. A normal 200 is expected; 206 is also safe.
        await RNFS.unlink(part).catch(() => {});
        await RNFS.moveFile(chunk, part);
      }

      const finalStat = await RNFS.stat(part);
      const finalSize = Number(finalStat.size);
      if (total !== undefined && finalSize !== total) {
        throw new Error(`incomplete download: ${finalSize} of ${total} bytes`);
      }

      const actualHash = await sha256(RNFS, part);
      if (expectedHash && actualHash && actualHash.toLowerCase() !== expectedHash.toLowerCase()) {
        await RNFS.unlink(part).catch(() => {});
        throw new Error('checksum mismatch');
      }

      const encrypted = await encryptOfflineFile({
        RNFS,
        sourcePath: part,
        encryptedPath: final,
        metadataPath: metadata,
        trackId: job.trackId,
        quality: job.quality,
        contentHash: expectedHash || actualHash || undefined,
      });
      return {
        path: encrypted.path,
        contentHash: expectedHash || actualHash || undefined,
        sizeBytes: finalSize,
        offlineLicense: res.offline_license,
        offlineLicenseExpiresAt: res.offline_license_expires_at,
      };
    } catch (error) {
      if (attempt === MAX_ATTEMPTS - 1) {
        throw error;
      }
      await sleep(RETRY_DELAYS_MS[attempt]);
    }
  }

  throw new Error('download retries exhausted');
}

export async function queueDownload(params: {
  trackId: string;
  title: string;
  quality?: AudioQuality;
}): Promise<DownloadJob> {
  const quality = params.quality || 'medium';
  const jobs = await listDownloadJobs();
  const id = jobId(params.trackId, quality);
  const existing = jobs.find(j => j.id === id);
  if (existing && (existing.status === 'queued' || existing.status === 'running')) {
    return existing;
  }

  const now = Date.now();
  const job: DownloadJob = {
    id,
    trackId: params.trackId,
    title: params.title,
    quality,
    status: 'queued',
    progress: 0,
    createdAt: now,
    updatedAt: now,
  };
  await saveDownloadJobs(jobs.filter(j => j.id !== id).concat(job));
  processQueue().catch(() => {});
  return job;
}

async function updateJob(
  id: string,
  patch: Partial<DownloadJob>,
): Promise<void> {
  const jobs = await listDownloadJobs();
  const next = jobs.map(j =>
    j.id === id ? {...j, ...patch, updatedAt: Date.now()} : j,
  );
  await saveDownloadJobs(next);
}

export async function processQueue(): Promise<void> {
  if (queueRunning) {
    return;
  }
  queueRunning = true;

  try {
    const RNFS = await loadRNFS();
    const dir = `${RNFS.DocumentDirectoryPath}/kubanfy/offline`;
    await ensureDir(RNFS, dir);
    await cleanupInterruptedKfyArtifacts(RNFS, dir);

    while (true) {
      const jobs = await listDownloadJobs();
      // A persisted "running" job is an interrupted job after app restart.
      const next = jobs.find(
        j => j.status === 'queued' || j.status === 'running',
      );
      if (!next) {
        return;
      }

      await updateJob(next.id, {status: 'running'});

      try {
        const result = await downloadWithResume(next);
        const meta: OfflineTrackMeta = {
          trackId: next.trackId,
          title: next.title,
          quality: next.quality,
          localUri: fileUri(result.path),
          downloadedAt: Date.now(),
          contentHash: result.contentHash,
          sizeBytes: result.sizeBytes,
          encrypted: true,
          offlineLicense: result.offlineLicense,
          offlineLicenseExpiresAt: result.offlineLicenseExpiresAt,
          licenseValidatedAt: Date.now(),
        };
        await upsertOfflineTrack(meta);
        await updateJob(next.id, {
          status: 'completed',
          progress: 1,
          bytesDownloaded: result.sizeBytes,
          totalBytes: result.sizeBytes,
        });
      } catch (e) {
        await updateJob(next.id, {
          status: 'failed',
          error: e instanceof Error ? e.message : 'download failed',
        });
      }
    }
  } finally {
    queueRunning = false;
  }
}

export async function cancelDownload(id: string): Promise<void> {
  const jobs = await listDownloadJobs();
  await saveDownloadJobs(
    jobs.map(j =>
      j.id === id && j.status !== 'completed'
        ? {...j, status: 'cancelled' as const, updatedAt: Date.now()}
        : j,
    ),
  );
}
