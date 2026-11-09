export type DownloadHeader = {
  version: number;
  content_hash: string;
  plaintext_size: number;
  quality: string;
  content_type: string;
  chunk_size: number;
  chunk_count: number;
};

export type OfflineDownloadIdentity = {
  contentHash: string;
  assetVersion: number;
  quality: string;
  totalChunks: number;
  headerEnd: number;
  chunkSize: number;
  headerBytesB64?: string;
};

export function kby2HeaderEnd(prefix: Uint8Array): number {
  if (
    prefix.byteLength !== 9 ||
    new TextDecoder().decode(prefix.subarray(0, 4)) !== "KBY2" ||
    prefix[4] !== 2
  ) {
    throw new Error("El prefijo del header KBY2 es inválido.");
  }
  const jsonLength = new DataView(
    prefix.buffer,
    prefix.byteOffset,
    prefix.byteLength,
  ).getUint32(5);
  if (!Number.isSafeInteger(jsonLength) || jsonLength < 2 || jsonLength > 64 * 1024) {
    throw new Error("El tamaño del header KBY2 está fuera de los límites permitidos.");
  }
  return 9 + jsonLength;
}

export function validateDownloadHeader(
  header: DownloadHeader,
  expectedContentHash: string,
  expectedQuality: string,
): void {
  if (header.version !== 2) throw new Error("La descarga requiere un contenedor KBY2.");
  if (header.content_hash?.toLowerCase() !== expectedContentHash.toLowerCase()) {
    throw new Error("El content hash del contenedor no coincide con el asset autorizado.");
  }
  if (header.quality?.toLowerCase() !== expectedQuality.toLowerCase()) {
    throw new Error("La calidad del contenedor no coincide con la descarga autorizada.");
  }
  if (typeof header.content_type !== "string" || !header.content_type.toLowerCase().startsWith("audio/")) {
    throw new Error("El contenedor KBY2 no declara un tipo de contenido de audio.");
  }
  if (
    !Number.isSafeInteger(header.plaintext_size) ||
    header.plaintext_size <= 0 ||
    !Number.isSafeInteger(header.chunk_size) ||
    header.chunk_size < 16 * 1024 ||
    header.chunk_size > 1024 * 1024
  ) {
    throw new Error("Las dimensiones del contenedor KBY2 son inválidas.");
  }
  const expectedChunks = Math.ceil(header.plaintext_size / header.chunk_size);
  if (
    !Number.isSafeInteger(header.chunk_count) ||
    header.chunk_count <= 0 ||
    header.chunk_count !== expectedChunks
  ) {
    throw new Error("El chunk count del contenedor KBY2 no coincide con su tamaño.");
  }
}

export function canResumeDownload(
  existing: OfflineDownloadIdentity | undefined,
  expected: OfflineDownloadIdentity,
): boolean {
  return Boolean(
    existing &&
      existing.contentHash.toLowerCase() === expected.contentHash.toLowerCase() &&
      existing.assetVersion === expected.assetVersion &&
      existing.quality.toLowerCase() === expected.quality.toLowerCase() &&
      existing.totalChunks === expected.totalChunks &&
      existing.headerEnd === expected.headerEnd &&
      existing.chunkSize === expected.chunkSize &&
      existing.headerBytesB64 === expected.headerBytesB64,
  );
}

/** Validates record framing and AES-GCM authentication before persistence as verified. */
export async function verifyEncryptedChunk(
  record: Uint8Array,
  header: DownloadHeader,
  index: number,
  decrypt: (record: Uint8Array, index: number) => Promise<Uint8Array>,
): Promise<Uint8Array> {
  if (!Number.isSafeInteger(index) || index < 0 || index >= header.chunk_count) {
    throw new RangeError("El índice del chunk KBY2 está fuera de rango.");
  }
  const expectedPlaintextLength =
    index === header.chunk_count - 1
      ? header.plaintext_size - header.chunk_size * index
      : header.chunk_size;
  const expectedRecordLength = 4 + 12 + expectedPlaintextLength + 16;
  if (record.byteLength !== expectedRecordLength) {
    throw new Error("El encrypted length del chunk KBY2 no coincide con el rango esperado.");
  }
  const plaintext = await decrypt(record, index);
  if (plaintext.byteLength !== expectedPlaintextLength) {
    throw new Error("La longitud autenticada del chunk KBY2 no coincide con el header.");
  }
  return plaintext;
}
