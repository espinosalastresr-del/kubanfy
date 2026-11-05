/** Shared helpers: resolve track id from heterogeneous API shapes + enrich metadata. */

import { getTrackDetail, type Track } from "./api";

/** Prefer target_id (favorites), then track_id (playlist rows / discovery), then id (full Track). */
export function resolveTrackId(row: unknown): string {
  if (!row || typeof row !== "object") return "";
  const r = row as Record<string, unknown>;
  if (typeof r.target_id === "string" && r.target_id) return r.target_id;
  if (typeof r.track_id === "string" && r.track_id) return r.track_id;
  // Favorite row: never use favorite.id as track id
  if (typeof r.target_type === "string" && typeof r.target_id === "string") return r.target_id;
  if (typeof r.id === "string" && r.id && r.target_type == null) return r.id;
  if (typeof r.id === "string") return r.id;
  return "";
}

export type EnrichedTrack = Track & {
  track_id: string;
  position?: number;
  added_at?: string;
  favorite_id?: string;
};

/** Parallel getTrackDetail with soft fallbacks (never throws the whole batch). */
export async function enrichTrackIds(
  rows: Array<{ trackId: string; position?: number; added_at?: string; favorite_id?: string }>,
): Promise<EnrichedTrack[]> {
  const results = await Promise.all(
    rows.map(async (row) => {
      try {
        const detail = await getTrackDetail(row.trackId);
        return {
          ...detail,
          track_id: detail.id || row.trackId,
          position: row.position,
          added_at: row.added_at,
          favorite_id: row.favorite_id,
        } satisfies EnrichedTrack;
      } catch {
        return {
          id: row.trackId,
          track_id: row.trackId,
          title: "Canción",
          duration: null,
          artists: [],
          position: row.position,
          added_at: row.added_at,
          favorite_id: row.favorite_id,
        } satisfies EnrichedTrack;
      }
    }),
  );
  return results;
}
