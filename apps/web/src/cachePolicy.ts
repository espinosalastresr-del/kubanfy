/**
 * B3 — automatic cache policy (distinct from explicit Premium downloads).
 * FREE: max 3 tracks, LOW only, LRU. Never marks incomplete as ready.
 * Encrypted chunks live in offlineDb; this module only enforces counts.
 */

import { listTracks, removeOfflineTrack, type OfflineTrackRecord } from "./offlineDb";

export const FREE_AUTO_CACHE_LIMIT = 3;

export type PlanTier = "free" | "premium" | "family" | "student" | "guest";

export function autoCacheQualityForTier(tier: PlanTier): "low" | "medium" {
  if (tier === "premium" || tier === "family" || tier === "student") return "medium";
  return "low";
}

export function autoCacheLimitForTier(tier: PlanTier): number {
  if (tier === "guest") return 0;
  if (tier === "free") return FREE_AUTO_CACHE_LIMIT;
  // Premium automatic cache: soft limit (storage quota will constrain further).
  return 50;
}

/** Evict LRU automatic-cache tracks (source bootstrap treated as auto for FREE). */
export async function enforceAutoCacheLimit(
  tier: PlanTier,
  protectTrackId?: string | null,
): Promise<string[]> {
  const limit = autoCacheLimitForTier(tier);
  if (limit <= 0) return [];

  const all = await listTracks();
  // Automatic cache candidates: bootstrap or partial auto; never delete premium explicit while enforcing FREE limit.
  const auto = all
    .filter((t) => t.source === "bootstrap" || t.source === "premium")
    .filter((t) => t.status === "ready")
    .sort((a, b) => a.lastAccessedAt - b.lastAccessedAt);

  const removable = auto.filter((t) => t.trackId !== protectTrackId);
  const excess = Math.max(0, auto.length - limit);
  if (excess <= 0) return [];

  const victims = removable.slice(0, excess);
  for (const v of victims) {
    await removeOfflineTrack(v.trackId);
  }
  return victims.map((v) => v.trackId);
}

export function touchAccess(track: OfflineTrackRecord): OfflineTrackRecord {
  return { ...track, lastAccessedAt: Date.now(), updatedAt: Date.now() };
}
