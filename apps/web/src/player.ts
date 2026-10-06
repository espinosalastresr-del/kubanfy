import { playback, startPlayback, heartbeat } from "./api";
import { chunkRange, decryptChunk, parseHeader, parseTopLevelBoxes, type KbyHeader } from "./kby2";

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
  onState?: (state: string) => void;

  get element() { return this.audio; }

  async load(trackId: string, quality: "low" | "medium") {
    this.stop();
    this.onState?.("autorizando…");
    const meta = await playback(trackId, quality);
    if (meta.kby_version !== 2 || meta.streaming_format !== "fmp4") throw new Error("El backend no entregó un asset web compatible");
    this.url = meta.url;
    this.key = meta.kby_key;
    this.nextChunk = 0;
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
      const ok = () => { cleanup(); resolve(); };
      const fail = () => { cleanup(); reject(new Error("MediaSource no pudo inicializarse")); };
      const cleanup = () => {
        this.media?.removeEventListener("sourceopen", ok);
        this.media?.removeEventListener("error", fail);
      };
      this.media!.addEventListener("sourceopen", ok);
      this.media!.addEventListener("error", fail);
    });
    this.source = this.media.addSourceBuffer("audio/mp4; codecs=\"mp4a.40.2\"");
    this.onState?.("descifrando…");
    const playbackSession = await startPlayback(trackId, quality);\n    this.session = { session_id: playbackSession.playback_session_id, token: playbackSession.playback_token };
    this.startHeartbeat(trackId, quality);
    void this.pump();
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
      this.nextChunk += 1;
      this.onState?.(`cargando ${Math.round(this.nextChunk / this.header.chunk_count * 100)}%`);
      if (this.audio.paused && this.nextChunk >= 1) void this.audio.play().catch(() => {});
    }
    this.onState?.("listo");
  }

  private async flushQueue() {
    if (!this.source) return;
    while (this.appendQueue.length) {
      const box = this.appendQueue.shift()!;
      await new Promise<void>((resolve, reject) => {
        const append = () => {
          try { this.source!.appendBuffer(box); } catch (e) { reject(e); return; }
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
    if (this.timer) window.clearInterval(this.timer);
    this.timer = null;
    this.session = null;
    this.appendQueue = [];
    this.buffer = new Uint8Array();
    this.nextChunk = 0;
    this.header = null;
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
    this.objectUrl = "";
    this.media = null;
    this.source = null;
    this.audio.pause();
    this.audio.removeAttribute("src");
    this.audio.load();
  }
}
