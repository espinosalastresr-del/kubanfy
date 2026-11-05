/** Playback queue helpers (no network). */
export type QueueTrackMeta = {
  title: string;
  artists: string;
  artwork?: string | null;
};

export function trackArtistsLabel(track: any): string {
  if (!track) return "KubanFy";
  if (Array.isArray(track.artists)) {
    return track.artists.map((artist: any) => (typeof artist === "string" ? artist : artist?.name)).filter(Boolean).join(", ") || "KubanFy";
  }
  return track.artist || "KubanFy";
}

export function mergeQueueMeta(
  prev: Record<string, QueueTrackMeta>,
  tracks: any[],
): Record<string, QueueTrackMeta> {
  const next = { ...prev };
  for (const track of tracks) {
    const tid = track?.track_id ?? track?.id;
    if (!tid || typeof tid !== "string") continue;
    next[tid] = {
      title: track.title || next[tid]?.title || "Canción",
      artists: trackArtistsLabel(track) || next[tid]?.artists || "KubanFy",
      artwork: track.artwork_url || track.artwork || next[tid]?.artwork || null,
    };
  }
  return next;
}

export function buildDefaultQueue(currentId: string, known: any[]): string[] {
  return Array.from(
    new Set([currentId, ...known.map((track: any) => track.track_id ?? track.id).filter(Boolean)]),
  );
}
