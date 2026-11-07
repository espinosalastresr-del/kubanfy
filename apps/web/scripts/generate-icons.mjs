import { mkdir, writeFile } from "node:fs/promises";
import { deflateSync } from "node:zlib";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../dist");
const crcTable = new Uint32Array(256);
for (let n = 0; n < 256; n++) {
  let c = n;
  for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
  crcTable[n] = c >>> 0;
}
function crc32(bytes) {
  let c = 0xffffffff;
  for (const b of bytes) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const name = Buffer.from(type);
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0);
  name.copy(out, 4);
  data.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
}
function insideRoundRect(x, y, size, radius) {
  const cx = Math.max(radius, Math.min(size - radius - 1, x));
  const cy = Math.max(radius, Math.min(size - radius - 1, y));
  const dx = x - cx, dy = y - cy;
  return dx * dx + dy * dy <= radius * radius;
}
function render(size) {
  const raw = Buffer.alloc((size * 4 + 1) * size);
  const scale = size / 512;
  const putRect = (x, y, w, h, color, px, py) =>
    px >= x * scale && px < (x + w) * scale && py >= y * scale && py < (y + h) * scale;
  for (let y = 0; y < size; y++) {
    const row = y * (size * 4 + 1);
    raw[row] = 0;
    for (let x = 0; x < size; x++) {
      let rgba = [9, 9, 11, 255];
      const px = x + 0.5, py = y + 0.5;
      const bars = putRect(92, 150, 310, 56, null, px, py) ||
        putRect(92, 228, 224, 56, null, px, py) ||
        putRect(92, 306, 310, 56, null, px, py);
      if (bars) rgba = [255, 255, 255, 255];
      const dx = px - 386 * scale, dy = py - 256 * scale;
      if (dx * dx + dy * dy <= (44 * scale) ** 2) rgba = [245, 197, 66, 255];
      const i = row + 1 + x * 4;
      raw[i] = rgba[0]; raw[i + 1] = rgba[1]; raw[i + 2] = rgba[2]; raw[i + 3] = rgba[3];
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; ihdr[9] = 6;
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}
await mkdir(root, { recursive: true });
for (const [name, size] of [["icon-192.png",192],["icon-512.png",512],["apple-touch-icon.png",180],["favicon-32.png",32]]) {
  await writeFile(resolve(root, name), render(size));
}
console.log("Generated KubanFy PWA icons in dist/");
