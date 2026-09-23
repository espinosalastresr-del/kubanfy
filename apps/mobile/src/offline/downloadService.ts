/**
 * Download queue: API signed URL → local file.
 * Without native FS module, records job state and keeps remote URI as fallback.
 * When `react-native-fs` is linked, set USE_NATIVE_FS and implement write path.
 */

import {apiRequest} from '../api/client';
import {
  listDownloadJobs,
  saveDownloadJobs,
  upsertOfflineTrack,
} from './storage';
import {AudioQuality, DownloadJob, OfflineTrackMeta} from './types';

const USE_NATIVE_FS = false;

type DownloadResponse = {
  url?: string;
  signed_url?: string;
  track_id?: string;
  quality?: string;
};

function jobId(trackId: string, quality: AudioQuality): string {
  return `${trackId}:${quality}`;
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

  const job: DownloadJob = {
    id,
    trackId: params.trackId,
    title: params.title,
    quality,
    status: 'queued',
    progress: 0,
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
  const next = jobs.filter(j => j.id !== id).concat(job);
  await saveDownloadJobs(next);
  // Fire and forget processor
  processQueue().catch(() => {});
  return job;
}

export async function processQueue(): Promise<void> {
  const jobs = await listDownloadJobs();
  const next = jobs.find(j => j.status === 'queued');
  if (!next) {
    return;
  }
  await updateJob(next.id, {status: 'running', progress: 0.05});

  try {
    const res = await apiRequest<DownloadResponse>('/v1/music/download', {
      method: 'POST',
      body: JSON.stringify({track_id: next.trackId, quality: next.quality}),
    });
    const url = res.url || res.signed_url;
    if (!url) {
      throw new Error('No signed URL from server');
    }

    await updateJob(next.id, {progress: 0.4});

    let localUri = url;
    if (USE_NATIVE_FS) {
      // Placeholder: RNFS.downloadFile({ fromUrl: url, toFile: path })
      localUri = url;
    }

    const meta: OfflineTrackMeta = {
      trackId: next.trackId,
      title: next.title,
      quality: next.quality,
      localUri,
      downloadedAt: Date.now(),
    };
    await upsertOfflineTrack(meta);
    await updateJob(next.id, {status: 'completed', progress: 1});
  } catch (e) {
    const message = e instanceof Error ? e.message : 'Download failed';
    await updateJob(next.id, {status: 'failed', error: message, progress: 0});
  }

  // Continue with next queued
  await processQueue();
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

export async function cancelDownload(id: string): Promise<void> {
  const jobs = await listDownloadJobs();
  await saveDownloadJobs(
    jobs.map(j =>
      j.id === id && j.status === 'queued'
        ? {...j, status: 'cancelled', updatedAt: Date.now()}
        : j,
    ),
  );
}
