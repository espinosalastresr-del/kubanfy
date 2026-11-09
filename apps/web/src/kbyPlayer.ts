import { playback, startPlayback, heartbeat } from "./api";
import { chunkRange, decryptChunk, parseHeader, parseTopLevelBoxes, type KbyHeader } from "./kby2";
import {
  bindSessionActions, clearSession, setSessionMetadata, setSessionPlaybackState,
  setSessionPositionState, type SessionTrackMeta,
} from "./mediaSession";
import { isTrackReadyOffline, loadOfflineTrackMeta, readOfflineChunk } from "./offlinePlayback";
import { AutoCacheSession, type PlanTier } from "./autoCache";
import { touchTrackAccess } from "./offlineDb";
import { fetchRange } from "./rangeTransport";

type PlaybackOperation = { generation: number; controller: AbortController; signal: AbortSignal };

function operationAbortError() {
  return new DOMException("La reproducción fue sustituida o cancelada.", "AbortError");
}

/** KBY2 fMP4 MSE player: online Range + offline IndexedDB. Media Session + iOS playsinline. */
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
  private headerBytes: Uint8Array<ArrayBufferLike> = new Uint8Array();
  private key = "";
  private url = "";
  private objectUrl = "";
  private appendQueue: Uint8Array[] = [];
  private attemptedAutoplay = false;
  private audioMounted = false;
  private sessionBound = false;
  private offlineQuality = "low";
  private autoCache: AutoCacheSession | null = null;
  private planTier: PlanTier = "free";
  private currentTrackMeta: { title?: string; duration?: number | null; artworkUrl?: string | null } = {};
  private generation = 0;
  private abortController: AbortController | null = null;

  onState?: (s: string) => void;
  onProgress?: (t: number, d: number) => void;
  onPlayState?: (p: boolean) => void;
  onPlaybackChange?: (p: boolean) => void;
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
    this.audio.addEventListener("play", () => { this.emitPlayState(true); setSessionPlaybackState("playing"); });
    this.audio.addEventListener("pause", () => { this.emitPlayState(false); setSessionPlaybackState("paused"); });
    this.audio.addEventListener("ended", () => { setSessionPlaybackState("paused"); this.onEnded?.(); });
    this.audio.addEventListener("error", () => this.onState?.("Error de reproducción"));
  }

  get element() { return this.audio; }

  /** Furthest currently buffered media time; sequential KBY2 seeks stay within this window. */
  getBufferedEnd(): number {
    let end = 0;
    try {
      for (let index = 0; index < this.audio.buffered.length; index += 1) {
        end = Math.max(end, this.audio.buffered.end(index));
      }
    } catch {
      return 0;
    }
    return Number.isFinite(end) ? end : 0;
  }

  async playTrack(trackId: string, quality: "low" | "medium" = "low", userId?: string) {
    const operation = this.beginOperation();
    try {
      const readyOffline = await isTrackReadyOffline(trackId);
      if (!this.isCurrent(operation)) return;
      if (readyOffline) {
        try {
          await this.loadOffline(trackId, operation, userId);
        } catch (offlineError) {
          if (!this.isCurrent(operation)) return;
          // An expired or locally unverifiable license must not block normal
          // online playback when the API is reachable. Offline-only playback
          // remains fail-closed.
          if (typeof navigator !== "undefined" && navigator.onLine) {
            await this.load(trackId, quality, operation);
          } else {
            throw offlineError;
          }
        }
      } else {
        await this.load(trackId, quality, operation);
      }
    } catch (error) {
      if (this.isCurrent(operation)) throw error;
    }
  }

  async playOffline(trackId: string, userId?: string) {
    const operation = this.beginOperation();
    try {
      await this.loadOffline(trackId, operation, userId);
    } catch (error) {
      if (this.isCurrent(operation)) throw error;
    }
  }

  private beginOperation(): PlaybackOperation {
    this.stop(false);
    const controller = new AbortController();
    this.abortController = controller;
    return { generation: this.generation, controller, signal: controller.signal };
  }

  private isCurrent(operation: PlaybackOperation): boolean {
    return this.generation === operation.generation && !operation.signal.aborted;
  }

  /** App sets entitlement tier for auto-cache policy (guest disables). */
  setPlanTier(tier: PlanTier) {
    this.planTier = tier;
  }

  /** Optional metadata for auto-cache record labels. */
  setTrackInfo(info: { title?: string; duration?: number | null; artworkUrl?: string | null }) {
    this.currentTrackMeta = info || {};
  }

  togglePlayback() {
    if (this.audio.paused) return this.audio.play();
    this.audio.pause();
  }

  seek(seconds: number) {
    const duration = this.safeDuration();
    if (duration <= 0 || !Number.isFinite(seconds)) return;
    const target = Math.max(0, Math.min(seconds, duration));
    const ranges = this.audio.buffered;
    for (let index = 0; index < ranges.length; index += 1) {
      if (target >= ranges.start(index) && target <= ranges.end(index)) {
        this.audio.currentTime = target;
        return;
      }
    }
    // KBY2 currently streams sequentially; jumping outside the MSE window
    // would defeat backpressure by forcing every intervening chunk to download.
    this.onState?.("Ese tramo todavía no está cargado. Avanza dentro del audio disponible.");
  }

  setMetadata(track: SessionTrackMeta) {
    setSessionMetadata(track);
    this.ensureSessionActions();
  }

  updatePositionState() { this.syncPositionState(); }

  stop(clearMediaSession = true) {
    this.generation += 1;
    this.abortController?.abort();
    this.abortController = null;
    this.autoCache?.cancel();
    this.autoCache = null;
    if (this.timer) window.clearInterval(this.timer);
    this.timer = null;
    this.session = null;
    this.appendQueue = [];
    this.buffer = new Uint8Array();
    this.nextChunk = 0;
    this.attemptedAutoplay = false;
    this.header = null;
    this.headerEnd = 0;
    this.headerBytes = new Uint8Array();
    this.key = "";
    this.url = "";
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
    this.objectUrl = "";
    this.media = null;
    this.source = null;
    this.audio.pause();
    this.audio.removeAttribute("src");
    this.audio.load();
    setSessionPlaybackState("none");
    if (clearMediaSession) { clearSession(); this.sessionBound = false; }
  }

  private async openMse(operation: PlaybackOperation) {
    if (!this.isCurrent(operation)) throw operationAbortError();
    const media = new MediaSource();
    this.media = media;
    this.objectUrl = URL.createObjectURL(media);
    this.audio.src = this.objectUrl;
    await new Promise<void>((resolve, reject) => {
      const cleanup = () => {
        media.removeEventListener("sourceopen", ok);
        media.removeEventListener("error", fail);
        operation.signal.removeEventListener("abort", abort);
      };
      const ok = () => { cleanup(); resolve(); };
      const fail = () => { cleanup(); reject(new Error("MediaSource no pudo inicializarse")); };
      const abort = () => { cleanup(); reject(operationAbortError()); };
      if (operation.signal.aborted) { abort(); return; }
      media.addEventListener("sourceopen", ok, { once: true });
      media.addEventListener("error", fail, { once: true });
      operation.signal.addEventListener("abort", abort, { once: true });
    });
    if (!this.isCurrent(operation)) throw operationAbortError();
    this.source = media.addSourceBuffer('audio/mp4; codecs="mp4a.40.2"');
  }

  private async loadOffline(trackId: string, operation: PlaybackOperation, userId?: string) {
    this.ensureAudioInDom();
    this.ensureSessionActions();
    this.onState?.("offline…");
    void touchTrackAccess(trackId).catch(() => {});
    if (!userId) throw new Error("Inicia sesión para verificar la licencia offline.");
    const { track, header, headerBytes, key } = await loadOfflineTrackMeta(trackId, userId);
    if (!this.isCurrent(operation)) return;
    this.header = header;
    this.headerEnd = track.headerEnd;
    this.headerBytes = headerBytes;
    this.key = key;
    this.offlineQuality = track.quality || "low";
    this.nextChunk = 0;
    this.attemptedAutoplay = false;
    this.url = "";
    await this.openMse(operation);
    if (!this.isCurrent(operation)) return;
    this.onState?.("descifrando offline…");
    void this.pumpOffline(trackId, operation).catch((error) => {
      if (this.isCurrent(operation)) {
        this.onState?.(error instanceof Error ? error.message : "Error offline");
      }
    });
  }

  private async pumpOffline(trackId: string, operation: PlaybackOperation) {
    const header = this.header;
    const headerBytes = this.headerBytes;
    const key = this.key;
    if (!header || !this.source) return;
    while (this.isCurrent(operation) && this.nextChunk < header.chunk_count) {
      await this.waitForBufferRoom(operation);
      if (!this.isCurrent(operation)) return;
      const index = this.nextChunk;
      const record = await readOfflineChunk(trackId, this.offlineQuality, index);
      if (!this.isCurrent(operation)) return;
      const plaintext = await decryptChunk(record, headerBytes, index, key);
      if (!this.isCurrent(operation)) return;
      await this.feedPlaintext(plaintext, operation);
      if (!this.isCurrent(operation)) return;
      this.nextChunk = index + 1;
      this.onState?.(`offline ${Math.round((this.nextChunk / header.chunk_count) * 100)}%`);
      if (!this.attemptedAutoplay && this.nextChunk >= 1) {
        this.attemptedAutoplay = true;
        void this.audio.play().catch(() => {});
      }
    }
    if (!this.isCurrent(operation)) return;
    if (this.buffer.length) throw new Error("El flujo offline terminó con un fragmento fMP4 incompleto.");
    this.endStream();
    this.onState?.("listo offline");
  }

  async load(
    trackId: string,
    quality: "low" | "medium",
    operation: PlaybackOperation = this.beginOperation(),
  ) {
    this.ensureAudioInDom();
    this.ensureSessionActions();
    this.onState?.("autorizando…");
    const meta = await playback(trackId, quality);
    if (!this.isCurrent(operation)) return;
    if (meta.kby_version !== 2 || meta.streaming_format !== "fmp4") {
      throw new Error("El backend no entregó un asset web compatible");
    }
    this.url = meta.url;
    this.key = meta.kby_key;
    this.nextChunk = 0;
    this.attemptedAutoplay = false;
    const head = await fetchRange(meta.url, 0, 4095, operation.signal);
    if (!this.isCurrent(operation)) return;
    const parsed = parseHeader(head);
    if (
      parsed.header.chunk_count <= 0 ||
      parsed.header.chunk_size <= 0 ||
      parsed.header.plaintext_size <= 0
    ) {
      throw new Error("El header KBY2 contiene dimensiones inválidas.");
    }
    this.header = parsed.header;
    this.headerEnd = parsed.headerEnd;
    this.headerBytes = head.slice(9, this.headerEnd);

    this.autoCache?.cancel();
    const cacheSession = await AutoCacheSession.begin({
      trackId,
      title: this.currentTrackMeta.title || "Canción",
      duration: this.currentTrackMeta.duration ?? null,
      quality,
      contentHash: meta.content_hash,
      kbyKey: meta.kby_key,
      assetVersion: meta.asset_version ?? 1,
      header: this.header,
      headerEnd: this.headerEnd,
      headerJsonBytes: this.headerBytes,
      artworkUrl: this.currentTrackMeta.artworkUrl ?? null,
      tier: this.planTier,
    });
    if (!this.isCurrent(operation)) {
      cacheSession?.cancel();
      return;
    }
    this.autoCache = cacheSession;

    await this.openMse(operation);
    if (!this.isCurrent(operation)) return;
    this.onState?.("descifrando…");
    const ps = await startPlayback(trackId, quality);
    if (!this.isCurrent(operation)) return;
    this.session = { session_id: ps.playback_session_id, token: ps.playback_token };
    this.startHeartbeat();
    void this.pump(operation).catch((error) => {
      if (this.isCurrent(operation)) {
        this.autoCache?.cancel();
        this.autoCache = null;
        this.onState?.(error instanceof Error ? error.message : "Error cargando audio");
      }
    });
  }

  private async pump(operation: PlaybackOperation) {
    const header = this.header;
    const headerBytes = this.headerBytes;
    const key = this.key;
    const url = this.url;
    if (!header || !this.source) return;
    while (this.isCurrent(operation) && this.nextChunk < header.chunk_count) {
      await this.waitForBufferRoom(operation);
      if (!this.isCurrent(operation)) return;
      const index = this.nextChunk;
      const { start, end } = chunkRange(header, this.headerEnd, index);
      const record = await fetchRange(url, start, end, operation.signal);
      if (!this.isCurrent(operation)) return;
      const plaintext = await decryptChunk(record, headerBytes, index, key);
      if (!this.isCurrent(operation)) return;
      // Cache only after AES-GCM authentication succeeds.
      const cacheSession = this.autoCache;
      if (cacheSession) await cacheSession.storeChunk(index, record);
      if (!this.isCurrent(operation)) return;
      await this.feedPlaintext(plaintext, operation);
      if (!this.isCurrent(operation)) return;
      this.nextChunk = index + 1;
      this.onState?.(`cargando ${Math.round((this.nextChunk / header.chunk_count) * 100)}%`);
      if (!this.attemptedAutoplay && this.nextChunk >= 1) {
        this.attemptedAutoplay = true;
        void this.audio.play().catch(() => {});
      }
    }
    if (!this.isCurrent(operation)) return;
    if (this.buffer.length) throw new Error("El flujo terminó con un fragmento fMP4 incompleto.");
    this.endStream();
    if (this.autoCache) {
      await this.autoCache.finalize();
      if (!this.isCurrent(operation)) return;
      this.autoCache = null;
    }
    this.onState?.("listo");
  }

  private async feedPlaintext(plaintext: Uint8Array, operation: PlaybackOperation) {
    if (!this.isCurrent(operation)) return;
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
    await this.flushQueue(operation);
  }

  private endStream() {
    if (this.media?.readyState === "open" && !this.source?.updating) {
      try { this.media.endOfStream(); } catch { /* already ended */ }
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
      position: "fixed", width: "1px", height: "1px", opacity: "0",
      pointerEvents: "none", zIndex: "-1", bottom: "0", left: "0",
    });
    document.body.appendChild(this.audio);
    this.audioMounted = true;
  }

  private ensureSessionActions() {
    if (this.sessionBound) return;
    bindSessionActions({
      play: () => { void this.audio.play().catch(() => {}); },
      pause: () => this.audio.pause(),
      stop: () => this.stop(),
      seek: (s) => this.seek(s),
      seekBy: (d) => this.seek(this.audio.currentTime + d),
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

  private bufferAhead(): number {
    try {
      const current = this.audio.currentTime;
      const ranges = this.audio.buffered;
      for (let index = 0; index < ranges.length; index += 1) {
        const start = ranges.start(index);
        const end = ranges.end(index);
        if (current >= start - 0.25 && current <= end) return Math.max(0, end - current);
      }
    } catch {
      // MediaSource may not have exposed a buffered range yet.
    }
    return 0;
  }

  /** Pause network reads once enough playable media is queued; resume near the low-water mark. */
  private async waitForBufferRoom(operation: PlaybackOperation): Promise<void> {
    const highWaterSeconds = 18;
    const lowWaterSeconds = 9;
    if (!this.isCurrent(operation) || this.bufferAhead() < highWaterSeconds) return;
    await new Promise<void>((resolve) => {
      const cleanup = () => {
        this.audio.removeEventListener("timeupdate", check);
        this.audio.removeEventListener("play", check);
        this.audio.removeEventListener("seeking", check);
        operation.signal.removeEventListener("abort", abort);
      };
      const finish = () => { cleanup(); resolve(); };
      const check = () => {
        if (!this.isCurrent(operation) || this.bufferAhead() <= lowWaterSeconds) finish();
      };
      const abort = () => finish();
      if (operation.signal.aborted) { finish(); return; }
      this.audio.addEventListener("timeupdate", check);
      this.audio.addEventListener("play", check);
      this.audio.addEventListener("seeking", check);
      operation.signal.addEventListener("abort", abort, { once: true });
      check();
    });
  }

  private async flushQueue(operation: PlaybackOperation) {
    while (this.appendQueue.length && this.isCurrent(operation)) {
      const source = this.source;
      if (!source) return;
      const box = this.appendQueue.shift()!;
      await new Promise<void>((resolve, reject) => {
        const cleanup = () => {
          source.removeEventListener("updateend", done);
          source.removeEventListener("error", fail);
          source.removeEventListener("updateend", append);
          operation.signal.removeEventListener("abort", abort);
        };
        const done = () => { cleanup(); resolve(); };
        const fail = () => { cleanup(); reject(new Error("MSE append falló")); };
        const abort = () => { cleanup(); resolve(); };
        const append = () => {
          if (!this.isCurrent(operation) || this.source !== source) { abort(); return; }
          source.addEventListener("updateend", done, { once: true });
          source.addEventListener("error", fail, { once: true });
          try {
            source.appendBuffer(box.slice().buffer);
          } catch (error) {
            cleanup();
            reject(error);
          }
        };
        if (operation.signal.aborted) { abort(); return; }
        operation.signal.addEventListener("abort", abort, { once: true });
        if (source.updating) source.addEventListener("updateend", append, { once: true });
        else append();
      });
    }
  }

  private startHeartbeat() {
    const session = this.session;
    if (!session) return;
    const send = () => {
      if (this.session !== session) return;
      void heartbeat(session.token, this.audio.currentTime, this.audio.paused).catch(() => {});
    };
    send();
    this.timer = window.setInterval(send, 10000);
  }
}
