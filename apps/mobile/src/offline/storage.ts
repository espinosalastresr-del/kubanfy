/**
 * Offline catalog index (metadata). Binary audio lives on filesystem
 * once react-native-fs / expo-file-system-equivalent is wired in native builds.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import {
  DownloadJob,
  OfflineTrackMeta,
  PendingAnalyticsEvent,
} from './types';

const KEYS = {
  tracks: 'kubanfy.offline.tracks',
  downloads: 'kubanfy.offline.downloads',
  analyticsQueue: 'kubanfy.offline.analytics',
} as const;

async function readJson<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (!raw) {
      return fallback;
    }
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

async function writeJson(key: string, value: unknown): Promise<void> {
  await AsyncStorage.setItem(key, JSON.stringify(value));
}

export async function listOfflineTracks(): Promise<OfflineTrackMeta[]> {
  return readJson<OfflineTrackMeta[]>(KEYS.tracks, []);
}

export async function getOfflineTrack(
  trackId: string,
  quality?: string,
): Promise<OfflineTrackMeta | null> {
  const all = await listOfflineTracks();
  return (
    all.find(
      t => t.trackId === trackId && (!quality || t.quality === quality),
    ) || null
  );
}

export async function upsertOfflineTrack(meta: OfflineTrackMeta): Promise<void> {
  const all = await listOfflineTracks();
  const idx = all.findIndex(
    t => t.trackId === meta.trackId && t.quality === meta.quality,
  );
  if (idx >= 0) {
    all[idx] = meta;
  } else {
    all.push(meta);
  }
  await writeJson(KEYS.tracks, all);
}

export async function removeOfflineTrack(
  trackId: string,
  quality?: string,
): Promise<void> {
  const all = await listOfflineTracks();
  const next = all.filter(
    t => !(t.trackId === trackId && (!quality || t.quality === quality)),
  );
  await writeJson(KEYS.tracks, next);
}

export async function listDownloadJobs(): Promise<DownloadJob[]> {
  return readJson<DownloadJob[]>(KEYS.downloads, []);
}

export async function saveDownloadJobs(jobs: DownloadJob[]): Promise<void> {
  await writeJson(KEYS.downloads, jobs);
}

export async function enqueueAnalytics(
  event: PendingAnalyticsEvent,
): Promise<void> {
  const q = await readJson<PendingAnalyticsEvent[]>(KEYS.analyticsQueue, []);
  q.push(event);
  // Cap queue to avoid unbounded growth offline
  const trimmed = q.slice(-500);
  await writeJson(KEYS.analyticsQueue, trimmed);
}

export async function drainAnalyticsQueue(): Promise<PendingAnalyticsEvent[]> {
  const q = await readJson<PendingAnalyticsEvent[]>(KEYS.analyticsQueue, []);
  await writeJson(KEYS.analyticsQueue, []);
  return q;
}

export async function peekAnalyticsQueue(): Promise<PendingAnalyticsEvent[]> {
  return readJson<PendingAnalyticsEvent[]>(KEYS.analyticsQueue, []);
}
