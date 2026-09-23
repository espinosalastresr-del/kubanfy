/**
 * Download queue: API signed URL → local file (plan §46 / §91).
 * Uses react-native-fs when linked; otherwise keeps remote URI + job state.
 */

import {apiRequest} from '../api/client';
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
};

function jobId(trackId: string, quality: AudioQuality): string {
  return `${trackId}:${quality}`;
}

async function tryNativeDownload(
  url: string,
  trackId: string,
  quality: AudioQuality,
): Promise<string | null> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const RNFS = require('react-native-fs');
    const dir = `${RNFS.DocumentDirectoryPath}/kubanfy/offline`;
    const exists = await RNFS.exists(dir);
    if (!exists) {
      await RNFS.mkdir(dir);
    }
    const dest = `${dir}/${trackId}_${quality}.audio`;
    const result = await RNFS.downloadFile({
      fromUrl: url,
      toFile: dest,
      background: true,
      discretionary: true,
    }).promise;
    if (result.statusCode && result.statusCode >= 400) {
      return null;
    }
    return `file://${dest}`;
  } catch {
    return null;
  }
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

    await updateJob(next.id, {progress: 0.35});

    const nativePath = await tryNativeDownload(
      url,
      next.trackId,
      next.quality,
    );
    const localUri = nativePath || url;

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
    await updateJob(next.id, {
      status: 'failed',
      error: e instanceof Error ? e.message : 'download failed',
    });
  }

  // Continue with next job
  processQueue().catch(() => {});
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
