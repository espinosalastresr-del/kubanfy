/**
 * Automatic cache during online playback (≠ explicit Premium download).
 * FREE: LOW only, max 3 tracks, LRU. Guest: disabled.
 * Never marks incomplete as ready. Failures never block playback.
 */

import type { KbyHeader } from "./kby2";
import {
  getChunk,
  getTrack,
  headerBytesToB64,
  putChunk,
  putTrack,
  touchTrackAccess,
  type OfflineTrackRecord,
} from "./offlineDb";
import {
  autoCacheLimitForTier,
  autoCacheQualityForTier,
  enforceAutoCacheLimit,
  type PlanTier,
} from "./cachePolicy";

export type { PlanTier };

export type AutoCacheBeginOpts = {
  trackId: string;
  title: string;
  duration?: number | null;
  quality: string;
  contentHash: string;
  kbyKey: string;
  assetVersion: number;
  header: KbyHeader;
  headerEnd: number;
  headerJsonBytes: Uint8Array;
  artworkUrl?: string | null;
  tier: PlanTier;
};

export class AutoCacheSession {
  private trackId: string;
  private quality: string;
  private totalChunks: number;
  private completed = 0;
  private active = false;
  private tier: PlanTier;
  private record: OfflineTrackRecord | null = null;

  static async begin(opts: AutoCacheBeginOpts): Promise<AutoCacheSession | null> {
    const limit = autoCacheLimitForTier(opts.tier);
    if (limit <= 0) return null;

    const allowedQ = autoCacheQualityForTier(opts.tier);
    if (opts.tier === "free" && opts.quality !== "low") return null;
    if (opts.tier === "free" && allowedQ !== "low") return null;

    try {
      const existing = await getTrack(opts.trackId);
      if (
        existing &&
        existing.status === "ready" &&
        existing.contentHash === opts.contentHash &&
        existing.quality === opts.quality &&
        existing.headerBytesB64
      ) {
        await touchTrackAccess(opts.trackId);
        return null;
      }

      if (existing?.source === "premium" && existing.status === "ready") {
        await touchTrackAccess(opts.trackId);
        return null;
      }

      const totalChunks = opts.header.chunk_count;
      if (totalChunks <= 0) return null;

      const now = Date.now();
      const normalRecord = 4 + 12 + opts.header.chunk_size + 16;
      const lastPlain =
        opts.header.plaintext_size - opts.header.chunk_size * Math.max(0, totalChunks - 1);
      const lastRecord = 4 + 12 + lastPlain + 16;
      const totalEncrypted =
        opts.headerEnd + normalRecord * Math.max(0, totalChunks - 1) + lastRecord;

      const record: OfflineTrackRecord = {
        trackId: opts.trackId,
        title: opts.title,
        duration: opts.duration ?? null,
        quality: opts.quality,
        contentHash: opts.contentHash,
        assetVersion: opts.assetVersion,
        kbyKey: opts.kbyKey,
        headerBytesB64: headerBytesToB64(opts.headerJsonBytes),
        artworkUrl: opts.artworkUrl ?? null,
        source: "auto",
        status: "partial",
        totalChunks,
        completedChunks: 0,
        totalBytes: totalEncrypted,
        headerEnd: opts.headerEnd,
        chunkSize: opts.header.chunk_size,
        createdAt: existing?.createdAt ?? now,
        updatedAt: now,
        lastAccessedAt: now,
      };
      await putTrack(record);

      const session = new AutoCacheSession(opts.trackId, opts.quality, totalChunks, opts.tier);
      session.record = record;
      session.active = true;
      return session;
    } catch {
      return null;
    }
  }

  private constructor(trackId: string, quality: string, totalChunks: number, tier: PlanTier) {
    this.trackId = trackId;
    this.quality = quality;
    this.totalChunks = totalChunks;
    this.tier = tier;
  }

  async storeChunk(index: number, encrypted: Uint8Array): Promise<void> {
    if (!this.active || !this.record) return;
    try {
      const existing = await getChunk(this.trackId, this.quality, index);
      if (existing?.verified && existing.byteLength >= 8) {
        this.completed = Math.max(this.completed, index + 1);
        return;
      }
      if (encrypted.byteLength < 8) return;
      await putChunk({
        id: `${this.trackId}:${this.quality}:${index}`,
        trackId: this.trackId,
        quality: this.quality,
        chunkIndex: index,
        encryptedBytes: encrypted.buffer.slice(
          encrypted.byteOffset,
          encrypted.byteOffset + encrypted.byteLength,
        ),
        byteLength: encrypted.byteLength,
        verified: true,
        downloadedAt: Date.now(),
      });
      this.completed = Math.max(this.completed, index + 1);
      this.record = {
        ...this.record,
        completedChunks: this.completed,
        updatedAt: Date.now(),
        lastAccessedAt: Date.now(),
      };
      await putTrack(this.record);
    } catch {
      /* never block playback */
    }
  }

  async finalize(): Promise<void> {
    if (!this.active || !this.record) return;
    this.active = false;
    try {
      if (this.completed !== this.totalChunks || this.totalChunks <= 0) {
        this.record = {
          ...this.record,
          completedChunks: this.completed,
          status: "partial",
          updatedAt: Date.now(),
        };
        await putTrack(this.record);
        return;
      }
      this.record = {
        ...this.record,
        completedChunks: this.completed,
        status: "ready",
        updatedAt: Date.now(),
        lastAccessedAt: Date.now(),
      };
      await putTrack(this.record);
      await enforceAutoCacheLimit(this.tier, this.trackId);
    } catch {
      /* ignore */
    }
  }

  cancel(): void {
    this.active = false;
  }
}

export function tierFromUser(user: unknown): PlanTier {
  if (!user || typeof user !== "object") return "guest";
  const u = user as Record<string, unknown>;
  const plan =
    (typeof u.plan === "string" && u.plan) ||
    (typeof u.subscription === "string" && u.subscription) ||
    (typeof u.tier === "string" && u.tier) ||
    (u.entitlement &&
      typeof u.entitlement === "object" &&
      typeof (u.entitlement as { plan?: string }).plan === "string" &&
      (u.entitlement as { plan: string }).plan) ||
    "";
  const p = String(plan).toLowerCase();
  if (p.includes("premium") || p === "pro") return "premium";
  if (p.includes("family")) return "family";
  if (p.includes("student")) return "student";
  if (p.includes("guest")) return "guest";
  return "free";
}
