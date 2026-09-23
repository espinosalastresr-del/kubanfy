/** Chunked AES-256-GCM encryption for offline audio. */
import * as Keychain from 'react-native-keychain';
import crypto, {Buffer} from 'react-native-quick-crypto';

const KEY_SERVICE = 'com.kubanfy.offline-key';
const CHUNK_BYTES = 1024 * 1024;
const FORMAT = 'kubanfy-kfy-aes256gcm-v1';

type Envelope = {
  format: typeof FORMAT;
  iv: string;
  authTag: string;
  plaintextSize: number;
  contentHash?: string;
};

function keyService(trackId: string, quality: string, contentHash?: string): string {
  const suffix = contentHash || 'unknown';
  return KEY_SERVICE + '.' + trackId + '.' + quality + '.' + suffix;
}

async function getOrCreateKey(service: string): Promise<Buffer> {
  const existing = await Keychain.getGenericPassword({service});
  if (existing) return Buffer.from(existing.password, 'hex');
  const key = crypto.randomBytes(32);
  await Keychain.setGenericPassword('aes256', key.toString('hex'), {
    service,
    accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  return key;
}

async function getExistingKey(service: string): Promise<Buffer> {
  const existing = await Keychain.getGenericPassword({service});
  if (!existing) throw new Error('Offline audio key is unavailable');
  const key = Buffer.from(existing.password, 'hex');
  if (key.length !== 32) throw new Error('Invalid offline audio key');
  return key;
}

async function removeIfExists(RNFS: any, path: string): Promise<void> {
  if (await RNFS.exists(path)) await RNFS.unlink(path).catch(() => undefined);
}

export async function encryptOfflineFile(params: {
  RNFS: any; sourcePath: string; encryptedPath: string; metadataPath: string;
  trackId: string; quality: string; contentHash?: string;
}): Promise<{path: string; metadataPath: string}> {
  const {RNFS, sourcePath, encryptedPath, metadataPath, trackId, quality, contentHash} = params;
  const key = await getOrCreateKey(keyService(trackId, quality, contentHash));
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
  const plaintextSize = Number((await RNFS.stat(sourcePath)).size);
  const temp = encryptedPath + '.part';

  await removeIfExists(RNFS, temp);
  await removeIfExists(RNFS, encryptedPath);
  await removeIfExists(RNFS, metadataPath);

  let position = 0;
  while (position < plaintextSize) {
    const length = Math.min(CHUNK_BYTES, plaintextSize - position);
    const input = Buffer.from(await RNFS.read(sourcePath, length, position, 'base64'), 'base64');
    const output = cipher.update(input);
    if (output.length) await RNFS.appendFile(temp, output.toString('base64'), 'base64');
    position += length;
  }
  const finalChunk = cipher.final();
  if (finalChunk.length) await RNFS.appendFile(temp, finalChunk.toString('base64'), 'base64');

  const envelope: Envelope = {
    format: FORMAT,
    iv: iv.toString('base64'),
    authTag: cipher.getAuthTag().toString('base64'),
    plaintextSize,
    contentHash,
  };
  const metadataTemp = metadataPath + '.part';
  await removeIfExists(RNFS, metadataTemp);
  await RNFS.writeFile(metadataTemp, JSON.stringify(envelope), 'utf8');
  await RNFS.moveFile(temp, encryptedPath);
  await RNFS.moveFile(metadataTemp, metadataPath);
  await removeIfExists(RNFS, sourcePath);
  return {path: encryptedPath, metadataPath};
}

export async function decryptOfflineFile(params: {
  RNFS: any; encryptedPath: string; metadataPath: string; outputPath: string;
  trackId: string; quality: string; contentHash?: string;
}): Promise<string> {
  const {RNFS, encryptedPath, metadataPath, outputPath, trackId, quality, contentHash} = params;
  const envelope = JSON.parse(await RNFS.readFile(metadataPath, 'utf8')) as Envelope;
  if (envelope.format !== FORMAT || !envelope.iv || !envelope.authTag) {
    throw new Error('Unsupported offline audio format');
  }
  if (contentHash && envelope.contentHash && contentHash !== envelope.contentHash) {
    throw new Error('Offline audio content identity mismatch');
  }

  const key = await getExistingKey(keyService(trackId, quality, envelope.contentHash || contentHash));
  const decipher = crypto.createDecipheriv(
    'aes-256-gcm', key, Buffer.from(envelope.iv, 'base64'),
  );
  decipher.setAuthTag(Buffer.from(envelope.authTag, 'base64'));

  const ciphertextSize = Number((await RNFS.stat(encryptedPath)).size);
  const temp = outputPath + '.part';
  await removeIfExists(RNFS, temp);
  await removeIfExists(RNFS, outputPath);

  try {
    let position = 0;
    while (position < ciphertextSize) {
      const length = Math.min(CHUNK_BYTES, ciphertextSize - position);
      const input = Buffer.from(
        await RNFS.read(encryptedPath, length, position, 'base64'),
        'base64',
      );
      const output = decipher.update(input);
      if (output.length) await RNFS.appendFile(temp, output.toString('base64'), 'base64');
      position += length;
    }
    const finalChunk = decipher.final();
    if (finalChunk.length) await RNFS.appendFile(temp, finalChunk.toString('base64'), 'base64');

    const outputSize = Number((await RNFS.stat(temp)).size);
    if (outputSize !== envelope.plaintextSize) {
      throw new Error('Offline audio size verification failed');
    }
    await RNFS.moveFile(temp, outputPath);
  } catch (error) {
    // GCM authentication happens at final(). Never leave unauthenticated
    // plaintext behind if the ciphertext or metadata was tampered with.
    await removeIfExists(RNFS, temp);
    await removeIfExists(RNFS, outputPath);
    throw error;
  }
  return outputPath;
}

export async function removeOfflineKey(params: {
  trackId: string; quality: string; contentHash?: string;
}): Promise<void> {
  await Keychain.resetGenericPassword({
    service: keyService(params.trackId, params.quality, params.contentHash),
  });
}
