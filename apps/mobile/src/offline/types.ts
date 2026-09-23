/**
 * Offline-first types — aligned with plan §45–47.
 * Cache ≠ permanent download. Encrypted container is a later hardening step.
 */

export type AudioQuality = 'low' | 'medium' | 'lossless';

export type OfflineTrackMeta = {
  trackId: string;
  title: string;
  artistName?: string;
  duration?: number;
  quality: AudioQuality;
  /** Local filesystem URI (file://) */
  localUri: string;
  /** Content hash from server when available */
  contentHash?: string;
  downloadedAt: number;
  lastPlayedAt?: number;
  sizeBytes?: number;
};

export type DownloadJobStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type DownloadJob = {
  id: string;
  trackId: string;
  title: string;
  quality: AudioQuality;
  status: DownloadJobStatus;
  progress: number; // 0..1
  /** Durable state for process/network interruption. */
  bytesDownloaded?: number;
  totalBytes?: number;
  tempPath?: string;
  finalPath?: string;
  contentHash?: string;
  error?: string;
  createdAt: number;
  updatedAt: number;
};

export type PendingAnalyticsEvent = {
  event_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  createdAt: number;
};

export type PlayerTrack = {
  trackId: string;
  title: string;
  artistName?: string;
  /** Remote signed URL or local file URI */
  uri: string;
  duration?: number;
  isLocal: boolean;
  quality?: AudioQuality;
};
