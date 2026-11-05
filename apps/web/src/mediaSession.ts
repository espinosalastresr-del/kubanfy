/** Media Session helpers for lock-screen / OS media controls (B2). */
export type SessionTrackMeta = {
  title: string;
  artist: string;
  album?: string;
  artwork?: string | null;
};

export type SessionHandlers = {
  play: () => void;
  pause: () => void;
  seek: (seconds: number) => void;
  seekBy: (delta: number) => void;
  next?: () => void;
  previous?: () => void;
  stop?: () => void;
};

function hasMediaSession(): boolean {
  return typeof navigator !== "undefined" && "mediaSession" in navigator;
}

export function setSessionMetadata(track: SessionTrackMeta): void {
  if (!hasMediaSession()) return;
  try {
    const artwork = track.artwork
      ? [{ src: track.artwork, sizes: "512x512", type: "image/jpeg" as const }]
      : [];
    navigator.mediaSession.metadata = new MediaMetadata({
      title: track.title || "KubanFy",
      artist: track.artist || "Artista desconocido",
      album: track.album || "KubanFy",
      artwork,
    });
  } catch {
    /* MediaMetadata unsupported */
  }
}

export function bindSessionActions(handlers: SessionHandlers): void {
  if (!hasMediaSession()) return;
  const safe = (action: MediaSessionAction, handler: MediaSessionActionHandler) => {
    try {
      navigator.mediaSession.setActionHandler(action, handler);
    } catch {
      /* action not supported on this browser */
    }
  };

  safe("play", () => handlers.play());
  safe("pause", () => handlers.pause());
  safe("stop", () => handlers.stop?.() ?? handlers.pause());
  safe("seekbackward", (details) => handlers.seekBy(-(details.seekOffset || 10)));
  safe("seekforward", (details) => handlers.seekBy(details.seekOffset || 10));
  safe("seekto", (details) => {
    if (typeof details.seekTime === "number") handlers.seek(details.seekTime);
  });
  safe("nexttrack", () => handlers.next?.());
  safe("previoustrack", () => handlers.previous?.());
}

export function setSessionPlaybackState(state: MediaSessionPlaybackState): void {
  if (!hasMediaSession()) return;
  try {
    navigator.mediaSession.playbackState = state;
  } catch {
    /* ignore */
  }
}

export function setSessionPositionState(opts: {
  duration: number;
  position: number;
  playbackRate?: number;
}): void {
  if (!hasMediaSession() || !("setPositionState" in navigator.mediaSession)) return;
  const { duration, position, playbackRate = 1 } = opts;
  if (!Number.isFinite(duration) || duration <= 0) return;
  try {
    navigator.mediaSession.setPositionState({
      duration,
      playbackRate,
      position: Math.max(0, Math.min(position, duration)),
    });
  } catch {
    /* ignore invalid position */
  }
}

export function clearSession(): void {
  if (!hasMediaSession()) return;
  try {
    navigator.mediaSession.metadata = null;
    navigator.mediaSession.playbackState = "none";
  } catch {
    /* ignore */
  }
  const actions: MediaSessionAction[] = [
    "play",
    "pause",
    "stop",
    "seekbackward",
    "seekforward",
    "seekto",
    "nexttrack",
    "previoustrack",
  ];
  for (const action of actions) {
    try {
      navigator.mediaSession.setActionHandler(action, null);
    } catch {
      /* ignore */
    }
  }
}
