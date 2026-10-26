import { playback, startPlayback, heartbeat } from "./api";
import { chunkRange, decryptChunk, parseHeader, parseTopLevelBoxes, type KbyHeader } from "./kby2";
import type { OfflineTrack } from "./offline";


const RANGE_RETRIES = 5;

async function fetchRange(url: string, range: string): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= RANGE_RETRIES; attempt += 1) {
    try {
      const response = await fetch(url, { headers: { Range: range } });
      if (response.ok || ![408, 425, 429, 500, 502, 503, 504].includes(response.status) || attempt === RANGE_RETRIES) {
        return response;
      }
      lastError = new Error(`Solicitud de audio HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
      if (attempt === RANGE_RETRIES) throw error;
    }
    // Small exponential backoff avoids hammering mobile data during an outage.
    await new Promise(resolve => window.setTimeout(resolve, Math.min(8000, 500 * (2 ** attempt))));
  }
  throw lastError instanceof Error ? lastError : new Error("No se pudo descargar el audio");
}

function assertPartialRange(response: Response, requestedRange: string) {
  if (response.status !== 206) {
    throw new Error(`El servidor no respetó Range (${response.status}); se esperaba HTTP 206`);
  }
  const requested = requestedRange.match(/^bytes=(\d+)-(\d+)$/);
  const actual = response.headers.get("Content-Range")?.match(/^bytes (\d+)-(\d+)\/(\d+)$/);
  if (!requested || !actual) throw new Error("Respuesta de audio sin Content-Range válido");
  const requestedStart = Number(requested[1]);
  const requestedEnd = Number(requested[2]);
  const start = Number(actual[1]);
  const end = Number(actual[2]);
  const total = Number(actual[3]);
  if (
    start !== requestedStart ||
    end < start ||
    end > requestedEnd ||
    total <= end ||
    (end < requestedEnd && end !== total - 1)
  ) {
    throw new Error("El servidor devolvió un rango de audio incoherente");
  }
}

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
  private contentHash = "";
  private objectUrl = "";
  private appendQueue: Uint8Array[] = [];
  private generation = 0;
  private trackTitle = "KubanFy";
  private activeTrackId = "";
  private activeQuality: "low" | "medium" = "low";
  onState?: (state: string) => void;
  onNext?: () => void;
  onPrevious?: () => void;

  constructor() {
    // The audio element is mounted into the player surface; without controls,
    // mobile users could not pause, seek, or resume after an interruption.
    this.audio.controls = false;
    this.audio.preload = "metadata";
  }

  get element() { return this.audio; }
  get currentTime() { return this.audio.currentTime || 0; }
  get duration() { return Number.isFinite(this.audio.duration) ? this.audio.duration : 0; }
  get paused() { return this.audio.paused; }
  playPause() { return this.audio.paused ? this.audio.play() : Promise.resolve(this.audio.pause()); }
  seek(seconds: number) { if (Number.isFinite(this.audio.duration)) this.audio.currentTime = Math.max(0, Math.min(this.audio.duration, seconds)); }

  async load(trackId: string, quality: "low" | "medium", title = "KubanFy", artist = "KubanFy", artwork?: string | null) {
    this.stop();
    const generation = this.generation;
    this.trackTitle = title;
    this.activeTrackId = trackId;
    this.configureMediaSession(artist, artwork);
    this.activeQuality = quality;
    this.onState?.("autorizando…");
    const meta = await playback(trackId, quality);
    if (generation !== this.generation) return;
    if (meta.kby_version !== 2 || meta.streaming_format !== "fmp4") throw new Error("El backend no entregó un asset web compatible");
    this.url = meta.url;
    this.key = meta.kby_key;
    this.contentHash = meta.content_hash;
    this.nextChunk = 0;
    const headResponse = await this.fetchAudioRange("bytes=0-4095", trackId, quality);
    if (generation !== this.generation) return;
    const head = new Uint8Array(await headResponse.arrayBuffer());
    if (generation !== this.generation) return;
    const parsed = parseHeader(head);
    this.header = parsed.header;
    this.headerEnd = parsed.headerEnd;
    this.headerBytes = head.slice(9, this.headerEnd);

    await this.openMediaSource(generation);
    if (generation !== this.generation) return;
    this.onState?.("descifrando…");
    const playbackSession = await startPlayback(trackId, quality);
    if (generation !== this.generation) return;
    this.session = { session_id: playbackSession.playback_session_id, token: playbackSession.playback_token };
    this.startHeartbeat(trackId, quality);
    void this.pump(generation).catch(error => {
      if (generation !== this.generation) return;
      this.onState?.(error instanceof Error ? `Error de reproducción: ${error.message}` : "Error de reproducción");
    });
  }

  async loadOffline(track: OfflineTrack) {
    this.stop();
    const generation = this.generation;
    this.trackTitle = track.title;
    this.activeTrackId = track.trackId;
    this.activeQuality = track.quality;
    this.key = track.kbyKey;
    this.contentHash = track.contentHash;
    this.onState?.("verificando descarga offline…");

    const container = new Uint8Array(await track.blob.arrayBuffer());
    if (generation !== this.generation) return;
    const parsed = parseHeader(container);
    if (parsed.header.content_hash !== track.contentHash || parsed.header.quality !== track.quality) {
      throw new Error("La descarga no coincide con sus metadatos guardados.");
    }
    if (parsed.header.chunk_count < 1) throw new Error("La descarga no contiene audio.");
    const finalRange = chunkRange(parsed.header, parsed.headerEnd, parsed.header.chunk_count - 1);
    if (finalRange.end + 1 !== container.length) throw new Error("La descarga está incompleta; vuelve a descargarla.");
    this.header = parsed.header;
    this.headerEnd = parsed.headerEnd;
    this.headerBytes = container.slice(9, parsed.headerEnd);
    await this.openMediaSource(generation);
    if (generation !== this.generation) return;

    this.onState?.("reproduciendo descarga offline…");
    for (let index = 0; index < this.header.chunk_count; index += 1) {
      if (generation !== this.generation) return;
      const range = chunkRange(this.header, this.headerEnd, index);
      const plaintext = await decryptChunk(container.slice(range.start, range.end + 1), this.headerBytes, index, this.key);
      if (generation !== this.generation) return;
      await this.appendPlaintext(plaintext);
      this.nextChunk = index + 1;
      this.onState?.(`descarga offline ${Math.round(this.nextChunk / this.header.chunk_count * 100)}%`);
      if (this.audio.paused && index === 0) void this.audio.play().catch(() => {});
    }
    if (generation === this.generation) {
      if (this.media?.readyState === "open" && !this.source?.updating) {
        try { this.media.endOfStream(); } catch { /* Browser may close MSE automatically. */ }
      }
      this.onState?.("listo · modo offline");
    }
  }

  private async openMediaSource(generation: number) {
    this.media = new MediaSource();
    this.objectUrl = URL.createObjectURL(this.media);
    this.audio.src = this.objectUrl;
    this.configureMediaSession();
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
    if (generation !== this.generation) return;
    this.source = this.media.addSourceBuffer("audio/mp4; codecs=\"mp4a.40.2\"");
  }

  private async pump(generation: number) {
    if (!this.header || !this.source) return;
    while (generation === this.generation && this.nextChunk < this.header.chunk_count) {
      const { start, end } = chunkRange(this.header, this.headerEnd, this.nextChunk);
      const response = await this.fetchAudioRange(`bytes=${start}-${end}`, this.activeTrackId, this.activeQuality);
      if (generation !== this.generation) return;
      const record = new Uint8Array(await response.arrayBuffer());
      const plaintext = await decryptChunk(record, this.headerBytes, this.nextChunk, this.key);
      if (generation !== this.generation) return;
      await this.appendPlaintext(plaintext);
      this.nextChunk += 1;
      this.onState?.(`cargando ${Math.round(this.nextChunk / this.header.chunk_count * 100)}%`);
      if (this.audio.paused && this.nextChunk >= 1) void this.audio.play().catch(() => {});
    }
    if (generation === this.generation) {
      if (this.media?.readyState === "open" && !this.source?.updating) {
        try { this.media.endOfStream(); } catch { /* Some browsers close MSE automatically. */ }
      }
      this.onState?.("listo");
    }
  }

  private async fetchAudioRange(range: string, trackId: string, quality: "low" | "medium") {
    let response = await fetchRange(this.url, range);
    if ([401, 403, 410].includes(response.status)) {
      // Signed object URLs can expire during long playback or a mobile outage.
      // Re-authorize once, but never silently switch to different audio bytes.
      const renewed = await playback(trackId, quality);
      if (
        renewed.kby_version !== 2 ||
        renewed.streaming_format !== "fmp4" ||
        renewed.content_hash !== this.contentHash ||
        renewed.kby_key !== this.key
      ) {
        throw new Error("El audio cambió mientras se reproducía; vuelve a iniciar la canción");
      }
      this.url = renewed.url;
      response = await fetchRange(this.url, range);
    }
    assertPartialRange(response, range);
    return response;
  }

  private configureMediaSession(artist = "KubanFy", artwork?: string | null) {
    if (!("mediaSession" in navigator)) return;
    try {
      navigator.mediaSession.metadata = new MediaMetadata({ title: this.trackTitle, artist, ...(artwork ? { artwork: [{ src: artwork }] } : {}) });
      navigator.mediaSession.setActionHandler("play", () => { void this.audio.play().catch(() => {}); });
      navigator.mediaSession.setActionHandler("pause", () => this.audio.pause());
      navigator.mediaSession.setActionHandler("stop", () => this.stop());
      navigator.mediaSession.setActionHandler("nexttrack", () => this.onNext?.());
      navigator.mediaSession.setActionHandler("previoustrack", () => this.onPrevious?.());
      navigator.mediaSession.setActionHandler("seekto", details => { if (details.seekTime != null) this.audio.currentTime = details.seekTime; });
    } catch {
      // Media Session is optional and not supported consistently across browsers.
    }
  }

  private async appendPlaintext(plaintext: Uint8Array) {
    const combined = new Uint8Array(this.buffer.length + plaintext.length);
    combined.set(this.buffer); combined.set(plaintext, this.buffer.length);
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

  private async flushQueue() {
    if (!this.source) return;
    while (this.appendQueue.length) {
      const box = this.appendQueue.shift()!;
      await new Promise<void>((resolve, reject) => {
        const append = () => {
          try { this.source!.appendBuffer(box.slice().buffer); } catch (e) { reject(e); return; }
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

  private startHeartbeat(trackId: string, quality: string) {
    if (!this.session) return;
    const send = () => void heartbeat(
      this.session!.token,
      this.audio.currentTime,
      this.audio.paused,
    ).catch(() => {});
    send();
    this.timer = window.setInterval(send, 10000);
  }

  stop() {
    this.generation += 1;
    if ("mediaSession" in navigator) {
      try { navigator.mediaSession.metadata = null; } catch {}
    }
    if (this.timer) window.clearInterval(this.timer);
    this.timer = null;
    this.session = null;
    this.appendQueue = [];
    this.buffer = new Uint8Array();
    this.nextChunk = 0;
    this.header = null;
    this.key = "";
    this.url = "";
    this.contentHash = "";
    this.activeTrackId = "";
    this.activeQuality = "low";
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
    this.objectUrl = "";
    this.media = null;
    this.source = null;
    this.audio.pause();
    this.audio.removeAttribute("src");
    this.audio.load();
  }
}
