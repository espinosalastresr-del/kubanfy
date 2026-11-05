import { playback, startPlayback, heartbeat } from "./api";
import { chunkRange, decryptChunk, parseHeader, parseTopLevelBoxes, type KbyHeader } from "./kby2";
import {
  bindSessionActions,
  clearSession,
  setSessionMetadata,
  setSessionPlaybackState,
  setSessionPositionState,
  type SessionTrackMeta,
} from "./mediaSession";

/**
 * KBY2 fMP4 MSE player.
 * B2: Media Session (lock screen / headset) + iOS playsinline + audio mounted in DOM.
 */
export class KbyPlayer {
  private media: MediaSource | null = null;
  private source: SourceBuffer | null = null;
  private audio = new Audio();
  private session: { session_id: string; token: string } | null = null;
  private timer: number | null = null;
  private buffer = new Uint8Array();
  private nextChunk = 0;
  private header: KbyHeader | null = null;
  private headerEnd = 0;
  private headerBytes = new Uint8Array();
  private key = "";
  private url = "";
  private objectUrl = "";
  private appendQueue: Uint8Array[] = [];
  private attemptedAutoplay = false;
  private audioMounted = false;
  private sessionBound = false;

  onState?: (state: string) => void;
  onProgress?: (currentTime: number, duration: number) => void;
  /** Used by App */
  onPlayState?: (playing: boolean) => void;
  /** Alias for compatibility */
  onPlaybackChange?: (playing: boolean) => void;
  onEnded?: () => void;
  onNext?: () => void;
  onPrevious?: () => void;

  constructor() {
    this.configureAudioElement();
    this.audio.addEventListener("timeupdate", () => {
      this.onProgress?.(this.audio.currentTime, this.safeDuration());
      this.syncPositionState();
    });
    this.audio.addEventListener("durationchange", () => {
      this.onProgress?.(this.audio.currentTime, this.safeDuration());
      this.syncPositionState();
    });
    this.audio.addEventListener("play", () => {
      this.emitPlayState(true);
      setSessionPlaybackState("playing");
    });
    this.audio.addEventListener("pause", () => {
      this.emitPlayState(false);
      setSessionPlaybackState("paused");
    });
    this.audio.addEventListener("ended", () => {
      setSessionPlaybackState("paused");
      this.onEnded?.();
    });
    this.audio.addEventListener("error", () => this.onState?.("Error de reproducción"));
  }

  get element() {
    return this.audio;
  }

  /** App entry point */
  async playTrack(trackId: string, quality: "low" | "medium" = "low") {
    await this.load(trackId, quality);
  }

  togglePlayback() {
    if (this.audio.paused) return this.audio.play();
    this.audio.pause();
  }

  seek(seconds: number) {
    const duration = this.safeDuration();
    if (duration > 0) this.audio.currentTime = Math.max(0, Math.min(seconds, duration));
  }

  setMetadata(track: SessionTrackMeta) {
    setSessionMetadata(track);
    this.ensureSessionActions();
  }

  updatePositionState() {
    this.syncPositionState();
  }

  async load(trackId: string, quality: "low" | "medium") {
    this.stop(false);
    this.ensureAudioInDom();
    this.ensureSessionActions();
    this.onState?.("autorizando…");
    const meta = await playback(trackId, quality);
    if (meta.kby_version !== 2 || meta.streaming_format !== "fmp4") {
      throw new Error("El backend no entregó un asset web compatible");
    }
    this.url = meta.url;
    this.key = meta.kby_key;
    this.nextChunk = 0;
    this.attemptedAutoplay = false;
    const headResponse = await fetch(this.url, { headers: { Range: "bytes=0-4095" } });
    if (!headResponse.ok) throw new Error(`KBY2 header HTTP ${headResponse.status}`);
    const head = new Uint8Array(await headResponse.arrayBuffer());
    const parsed = parseHeader(head);
    this.header = parsed.header;
    this.headerEnd = parsed.headerEnd;
    this.headerBytes = head.slice(9, this.headerEnd);

    this.media = new MediaSource();
    this.objectUrl = URL.createObjectURL(this.media);
    this.audio.src = this.objectUrl;
    await new Promise<void>((resolve, reject) => {
      const ok = () => {
        cleanup();
        resolve();
      };
      const fail = () => {
        cleanup();
        reject(new Error("MediaSource no pudo inicializarse"));
      };
      const cleanup = () => {
        this.media?.removeEventListener("sourceopen", ok);
        this.media?.removeEventListener("error", fail);
      };
      this.media!.addEventListener("sourceopen", ok);
      this.media!.addEventListener("error", fail);
    });
    this.source = this.media.addSourceBuffer('audio/mp4; codecs="mp4a.40.2"');
    this.onState?.("descifrando…");
    const playbackSession = await startPlayback(trackId, quality);
    this.session = {
      session_id: playbackSession.playback_session_id,
      token: playbackSession.playback_token,
    };
    this.startHeartbeat(trackId, quality);
    void this.pump().catch((error) =>
      this.onState?.(error instanceof Error ? error.message : "Error cargando audio")
    );
  }

  stop(clearMediaSession = true) {
    if (this.timer) window.clearInterval(this.timer);
    this.timer = null;
    this.session = null;
    this.appendQueue = [];
    this.buffer = new Uint8Array();
    this.nextChunk = 0;
    this.attemptedAutoplay = false;
    this.header = null;
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
    this.objectUrl = "";
    this.media = null;
    this.source = null;
    this.audio.pause();
    this.audio.removeAttribute("src");
    this.audio.load();
    setSessionPlaybackState("none");
    if (clearMediaSession) {
      clearSession();
      this.sessionBound = false;
    }
  }

  private configureAudioElement() {
    this.audio.preload = "metadata";
    this.audio.setAttribute("playsinline", "true");
    this.audio.setAttribute("webkit-playsinline", "true");
    (this.audio as HTMLAudioElement & { playsInline?: boolean }).playsInline = true;
    this.audio.setAttribute("x-webkit-airplay", "allow");
  }

  private ensureAudioInDom() {
    if (this.audioMounted || typeof document === "undefined") return;
    this.audio.setAttribute("id", "kubanfy-audio");
    this.audio.setAttribute("aria-hidden", "true");
    Object.assign(this.audio.style, {
      position: "fixed",
      width: "1px",
      height: "1px",
      opacity: "0",
      pointerEvents: "none",
      zIndex: "-1",
      bottom: "0",
      left: "0",
    });
    document.body.appendChild(this.audio);
    this.audioMounted = true;
  }

  private ensureSessionActions() {
    if (this.sessionBound) return;
    bindSessionActions({
      play: () => {
        void this.audio.play().catch(() => {});
      },
      pause: () => this.audio.pause(),
      stop: () => this.stop(),
      seek: (seconds) => this.seek(seconds),
      seekBy: (delta) => this.seek(this.audio.currentTime + delta),
      next: () => this.onNext?.(),
      previous: () => this.onPrevious?.(),
    });
    this.sessionBound = true;
  }

  private emitPlayState(playing: boolean) {
    this.onPlayState?.(playing);
    this.onPlaybackChange?.(playing);
  }

  private safeDuration() {
    return Number.isFinite(this.audio.duration) ? this.audio.duration : 0;
  }

  private syncPositionState() {
    setSessionPositionState({
      duration: this.safeDuration(),
      position: this.audio.currentTime,
      playbackRate: this.audio.playbackRate || 1,
    });
  }

  private async pump() {
    if (!this.header || !this.source) return;
    while (this.nextChunk < this.header.chunk_count) {
      const { start, end } = chunkRange(this.header, this.headerEnd, this.nextChunk);
      const response = await fetch(this.url, { headers: { Range: `bytes=${start}-${end}` } });
      if (!response.ok) throw new Error(`KBY2 chunk HTTP ${response.status}`);
      const record = new Uint8Array(await response.arrayBuffer());
      const plaintext = await decryptChunk(record, this.headerBytes, this.nextChunk, this.key);
      const combined = new Uint8Array(this.buffer.length + plaintext.length);
      combined.set(this.buffer);
      combined.set(plaintext, this.buffer.length);
      this.buffer = combined;
      const parsed = parseTopLevelBoxes(this.buffer);
      for (const box of parsed.boxes) {
        if (box.type === "ftyp" || box.type === "moov" || box.type === "moof" || box.type === "mdat") {
          this.appendQueue.push(box.bytes);
        }
      }
      this.buffer = this.buffer.slice(parsed.consumed);
      await this.flushQueue();
      this.nextChunk += 1;
      this.onState?.(`cargando ${Math.round((this.nextChunk / this.header.chunk_count) * 100)}%`);
      if (!this.attemptedAutoplay && this.nextChunk >= 1) {
        this.attemptedAutoplay = true;
        void this.audio.play().catch(() => {});
      }
    }
    if (this.media?.readyState === "open" && !this.source?.updating) {
      try {
        this.media.endOfStream();
      } catch {
        /* already ended */
      }
    }
    this.onState?.("listo");
  }

  private async flushQueue() {
    if (!this.source) return;
    while (this.appendQueue.length) {
      const box = this.appendQueue.shift()!;
      await new Promise<void>((resolve, reject) => {
        const append = () => {
          try {
            this.source!.appendBuffer(box.slice().buffer);
          } catch (e) {
            reject(e);
            return;
          }
          const done = () => {
            cleanup();
            resolve();
          };
          const fail = () => {
            cleanup();
            reject(new Error("MSE append falló"));
          };
          const cleanup = () => {
            this.source?.removeEventListener("updateend", done);
            this.source?.removeEventListener("error", fail);
          };
          this.source!.addEventListener("updateend", done, { once: true });
          this.source!.addEventListener("error", fail, { once: true });
        };
        if (this.source!.updating) this.source!.addEventListener("updateend", append, { once: true });
        else append();
      });
    }
  }

  private startHeartbeat(_trackId: string, _quality: string) {
    if (!this.session) return;
    const send = () =>
      void heartbeat(this.session!.token, this.audio.currentTime, this.audio.paused).catch(() => {});
    send();
    this.timer = window.setInterval(send, 10000);
  }
}
