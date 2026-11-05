import { playback, startPlayback, heartbeat } from "./api";
import { chunkRange, decryptChunk, parseHeader, parseTopLevelBoxes, type KbyHeader } from "./kby2";
import {
  bindSessionActions, clearSession, setSessionMetadata, setSessionPlaybackState,
  setSessionPositionState, type SessionTrackMeta,
} from "./mediaSession";
import { isTrackReadyOffline, loadOfflineTrackMeta, readOfflineChunk } from "./offlinePlayback";
import { AutoCacheSession, type PlanTier } from "./autoCache";
import { touchTrackAccess } from "./offlineDb";

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

  async playTrack(trackId: string, quality: "low" | "medium" = "low") {
    if (await isTrackReadyOffline(trackId)) return this.loadOffline(trackId);
    return this.load(trackId, quality);
  }

  async playOffline(trackId: string) { return this.loadOffline(trackId); }

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
    const d = this.safeDuration();
    if (d > 0) this.audio.currentTime = Math.max(0, Math.min(seconds, d));
  }

  setMetadata(track: SessionTrackMeta) {
    setSessionMetadata(track);
    this.ensureSessionActions();
  }

  updatePositionState() { this.syncPositionState(); }

  stop(clearMediaSession = true) {
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

  private async openMse() {
    this.media = new MediaSource();
    this.objectUrl = URL.createObjectURL(this.media);
    this.audio.src = this.objectUrl;
    await new Promise<void>((resolve, reject) => {
      const ok = () => { cleanup(); resolve(); };
      const fail = () => { cleanup(); reject(new Error("MediaSource no pudo inicializarse")); };
      const cleanup = () => {
        this.media?.removeEventListener("sourceopen", ok);
        this.media?.removeEventListener("error", fail);
      };
      this.media!.addEventListener("sourceopen", ok);
      this.media!.addEventListener("error", fail);
    });
    this.source = this.media.addSourceBuffer('audio/mp4; codecs="mp4a.40.2"');
  }

  private async loadOffline(trackId: string) {
    this.stop(false);
    this.ensureAudioInDom();
    this.ensureSessionActions();
    this.onState?.("offline…");
    void touchTrackAccess(trackId).catch(() => {});
    const { track, header, headerBytes, key } = await loadOfflineTrackMeta(trackId);
    this.header = header;
    this.headerEnd = track.headerEnd;
    this.headerBytes = headerBytes;
    this.key = key;
    this.offlineQuality = track.quality || "low";
    this.nextChunk = 0;
    this.attemptedAutoplay = false;
    this.url = "";
    await this.openMse();
    this.onState?.("descifrando offline…");
    void this.pumpOffline(trackId).catch((e) =>
      this.onState?.(e instanceof Error ? e.message : "Error offline"),
    );
  }

  private async pumpOffline(trackId: string) {
    if (!this.header || !this.source) return;
    while (this.nextChunk < this.header.chunk_count) {
      const record = await readOfflineChunk(trackId, this.offlineQuality, this.nextChunk);
      await this.feedPlaintext(await decryptChunk(record, this.headerBytes, this.nextChunk, this.key));
      this.nextChunk += 1;
      this.onState?.(`offline ${Math.round((this.nextChunk / this.header.chunk_count) * 100)}%`);
      if (!this.attemptedAutoplay && this.nextChunk >= 1) {
        this.attemptedAutoplay = true;
        void this.audio.play().catch(() => {});
      }
    }
    this.endStream();
    this.onState?.("listo offline");
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

    this.autoCache?.cancel();
    this.autoCache = await AutoCacheSession.begin({
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

    await this.openMse();
    this.onState?.("descifrando…");
    const ps = await startPlayback(trackId, quality);
    this.session = { session_id: ps.playback_session_id, token: ps.playback_token };
    this.startHeartbeat();
    void this.pump().catch((e) =>
      this.onState?.(e instanceof Error ? e.message : "Error cargando audio"),
    );
  }

  private async pump() {
    if (!this.header || !this.source) return;
    while (this.nextChunk < this.header.chunk_count) {
      const { start, end } = chunkRange(this.header, this.headerEnd, this.nextChunk);
      const response = await fetch(this.url, { headers: { Range: `bytes=${start}-${end}` } });
      if (!response.ok) throw new Error(`KBY2 chunk HTTP ${response.status}`);
      const record = new Uint8Array(await response.arrayBuffer());
      if (this.autoCache) {
        await this.autoCache.storeChunk(this.nextChunk, record);
      }
      await this.feedPlaintext(await decryptChunk(record, this.headerBytes, this.nextChunk, this.key));
      this.nextChunk += 1;
      this.onState?.(`cargando ${Math.round((this.nextChunk / this.header.chunk_count) * 100)}%`);
      if (!this.attemptedAutoplay && this.nextChunk >= 1) {
        this.attemptedAutoplay = true;
        void this.audio.play().catch(() => {});
      }
    }
    this.endStream();
    if (this.autoCache) {
      await this.autoCache.finalize();
      this.autoCache = null;
    }
    this.onState?.("listo");
  }

  private async feedPlaintext(plaintext: Uint8Array) {
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

  private async flushQueue() {
    if (!this.source) return;
    while (this.appendQueue.length) {
      const box = this.appendQueue.shift()!;
      await new Promise<void>((resolve, reject) => {
        const append = () => {
          try { this.source!.appendBuffer(box.slice().buffer); }
          catch (e) { reject(e); return; }
          const done = () => { cleanup(); resolve(); };
          const fail = () => { cleanup(); reject(new Error("MSE append falló")); };
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

  private startHeartbeat() {
    if (!this.session) return;
    const send = () =>
      void heartbeat(this.session!.token, this.audio.currentTime, this.audio.paused).catch(() => {});
    send();
    this.timer = window.setInterval(send, 10000);
  }
}
