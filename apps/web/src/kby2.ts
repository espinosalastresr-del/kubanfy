const MAGIC = "KBY2";
const TAG = 16;
const NONCE = 12;

export type KbyHeader = {
  version: number; content_hash: string; plaintext_size: number; quality: string;
  content_type: string; chunk_size: number; chunk_count: number;
};

function u32(bytes: Uint8Array, offset: number) {
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(offset);
}
function u64(bytes: Uint8Array, offset: number) {
  return Number(new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getBigUint64(offset));
}

export function parseHeader(bytes: Uint8Array): { header: KbyHeader; headerEnd: number } {
  if (new TextDecoder().decode(bytes.subarray(0, 4)) !== MAGIC || bytes[4] !== 2) throw new Error("KBY2 header inválido");
  const length = u32(bytes, 5);
  const end = 9 + length;
  if (bytes.length < end) throw new Error("KBY2 header incompleto");
  const raw = JSON.parse(new TextDecoder().decode(bytes.subarray(9, end)));
  return { header: raw, headerEnd: end };
}

export function chunkOffset(header: KbyHeader, headerEnd: number, index: number) {
  const normal = 4 + NONCE + header.chunk_size + TAG;
  const last = header.chunk_count - 1;
  if (index === last) {
    const lastLen = header.plaintext_size - header.chunk_size * last;
    return headerEnd + normal * index;
  }
  return headerEnd + normal * index;
}

export function chunkLength(header: KbyHeader, index: number) {
  if (index !== header.chunk_count - 1) return header.chunk_size;
  return header.plaintext_size - header.chunk_size * index;
}

export function chunkRange(header: KbyHeader, headerEnd: number, index: number) {
  const start = chunkOffset(header, headerEnd, index);
  return { start, end: start + 4 + NONCE + chunkLength(header, index) + TAG - 1 };
}

export async function decryptChunk(
  record: Uint8Array, headerBytes: Uint8Array, index: number, keyBase64: string,
) {
  const len = u32(record, 0);
  const nonce = record.subarray(4, 4 + NONCE);
  const ciphertext = record.subarray(4 + NONCE);
  const keyRaw = Uint8Array.from(atob(keyBase64), c => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("raw", keyRaw, "AES-GCM", false, ["decrypt"]);
  const aad = new Uint8Array(4 + 1 + headerBytes.length + 8);
  aad.set(new TextEncoder().encode("KBY2"), 0);
  aad[4] = 2;
  aad.set(headerBytes, 5);
  new DataView(aad.buffer).setUint32(5 + headerBytes.length, index);
  new DataView(aad.buffer).setUint32(9 + headerBytes.length, len);
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce, additionalData: aad, tagLength: 128 }, key, ciphertext.slice().buffer);
  return new Uint8Array(plain);
}

export function parseTopLevelBoxes(buffer: Uint8Array) {
  const boxes: { type: string; bytes: Uint8Array }[] = [];
  let offset = 0;
  while (offset + 8 <= buffer.length) {
    const size = u32(buffer, offset);
    const type = new TextDecoder().decode(buffer.subarray(offset + 4, offset + 8));
    let boxSize = size;
    let headerSize = 8;
    if (size === 1) {
      if (offset + 16 > buffer.length) break;
      boxSize = u64(buffer, offset + 8);
      headerSize = 16;
    } else if (size === 0) boxSize = buffer.length - offset;
    if (boxSize < headerSize || offset + boxSize > buffer.length) break;
    boxes.push({ type, bytes: buffer.slice(offset, offset + boxSize) });
    offset += boxSize;
  }
  return { boxes, consumed: offset };
}
