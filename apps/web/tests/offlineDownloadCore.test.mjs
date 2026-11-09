import test from "node:test";
import assert from "node:assert/strict";
import { validateDownloadHeader, canResumeDownload, verifyEncryptedChunk, kby2HeaderEnd } from "../src/offlineDownloadCore.ts";
import { decryptChunk } from "../src/kby2.ts";

const HASH = "a".repeat(64);
const QUALITY = "medium";
const HEADER_BYTES = new TextEncoder().encode(JSON.stringify({
  version: 2,
  content_hash: HASH,
  plaintext_size: 5,
  quality: QUALITY,
  content_type: "audio/mp4",
  chunk_size: 16384,
  chunk_count: 1,
}));

function header(overrides = {}) {
  return {
    version: 2,
    content_hash: HASH,
    plaintext_size: 5,
    quality: QUALITY,
    content_type: "audio/mp4",
    chunk_size: 16384,
    chunk_count: 1,
    ...overrides,
  };
}

function track(overrides = {}) {
  return {
    contentHash: HASH,
    assetVersion: 4,
    quality: QUALITY,
    totalChunks: 1,
    headerEnd: 128,
    chunkSize: 16384,
    headerBytesB64: "aGVhZGVy",
    ...overrides,
  };
}

async function encryptedRecord(plaintext) {
  const keyBytes = crypto.getRandomValues(new Uint8Array(32));
  const key = Buffer.from(keyBytes).toString("base64");
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const aad = new Uint8Array(4 + 1 + HEADER_BYTES.length + 8);
  aad.set(new TextEncoder().encode("KBY2"), 0);
  aad[4] = 2;
  aad.set(HEADER_BYTES, 5);
  new DataView(aad.buffer).setUint32(5 + HEADER_BYTES.length, 0);
  new DataView(aad.buffer).setUint32(9 + HEADER_BYTES.length, plaintext.length);
  const cryptoKey = await crypto.subtle.importKey("raw", keyBytes, "AES-GCM", false, ["encrypt"]);
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce, additionalData: aad, tagLength: 128 },
    cryptoKey,
    plaintext,
  ));
  const record = new Uint8Array(4 + nonce.length + ciphertext.length);
  new DataView(record.buffer).setUint32(0, plaintext.length);
  record.set(nonce, 4);
  record.set(ciphertext, 4 + nonce.length);
  return { record, key };
}

test("accepts a valid KBY2 header matching the requested asset", () => {
  assert.doesNotThrow(() => validateDownloadHeader(header(), HASH, QUALITY));
});

test("accepts supported audio content types used by the encoder", () => {
  assert.doesNotThrow(() => validateDownloadHeader(header({ content_type: "audio/mpeg" }), HASH, QUALITY));
});

test("rejects a KBY2 header for a different content hash", () => {
  assert.throws(() => validateDownloadHeader(header(), "b".repeat(64), QUALITY), /content hash/);
});

test("rejects invalid chunk dimensions instead of creating a ready download", () => {
  assert.throws(() => validateDownloadHeader(header({ chunk_count: 2 }), HASH, QUALITY), /chunk count/);
});

test("resumes only when content hash, asset version, quality and header identity match", () => {
  assert.equal(canResumeDownload(track(), track()), true);
  assert.equal(canResumeDownload(track(), track({ assetVersion: 5 })), false);
  assert.equal(canResumeDownload(track(), track({ contentHash: "b".repeat(64) })), false);
  assert.equal(canResumeDownload(track(), track({ quality: "low" })), false);
  assert.equal(canResumeDownload(track(), track({ headerBytesB64: "different" })), false);
  assert.equal(canResumeDownload(track({ headerBytesB64: undefined }), track()), false);
});

test("authenticates a downloaded AES-GCM chunk before it can be marked verified", async () => {
  const plaintext = new TextEncoder().encode("audio");
  const { record, key } = await encryptedRecord(plaintext);
  const result = await verifyEncryptedChunk(
    record,
    header(),
    0,
    (chunk, index) => decryptChunk(chunk, HEADER_BYTES, index, key),
  );
  assert.deepEqual([...result], [...plaintext]);
});

test("rejects a chunk whose AES-GCM authentication tag was modified", async () => {
  const plaintext = new TextEncoder().encode("audio");
  const { record, key } = await encryptedRecord(plaintext);
  record[record.length - 1] ^= 0xff;
  await assert.rejects(
    verifyEncryptedChunk(record, header(), 0, (chunk, index) => decryptChunk(chunk, HEADER_BYTES, index, key)),
  );
});

test("rejects encrypted chunks with a truncated or unexpected record length", async () => {
  const plaintext = new TextEncoder().encode("audio");
  const { record } = await encryptedRecord(plaintext);
  await assert.rejects(
    verifyEncryptedChunk(record.subarray(0, record.length - 1), header(), 0, async () => plaintext),
    /encrypted length/,
  );
});

test("reads the exact KBY2 header boundary without assuming the asset is 8 KiB", () => {
  const prefix = new Uint8Array(9);
  prefix.set(new TextEncoder().encode("KBY2"));
  prefix[4] = 2;
  new DataView(prefix.buffer).setUint32(5, 127);
  assert.equal(kby2HeaderEnd(prefix), 136);
});

test("rejects malformed or oversized KBY2 header prefixes", () => {
  assert.throws(() => kby2HeaderEnd(new Uint8Array(8)), /prefijo/);
  const prefix = new Uint8Array(9);
  prefix.set(new TextEncoder().encode("KBY2"));
  prefix[4] = 2;
  new DataView(prefix.buffer).setUint32(5, 65 * 1024);
  assert.throws(() => kby2HeaderEnd(prefix), /fuera de los límites/);
});
