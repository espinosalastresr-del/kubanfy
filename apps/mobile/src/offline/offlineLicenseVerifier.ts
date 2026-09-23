/** Offline-license verification performed entirely on-device. */
import crypto, {Buffer} from 'react-native-quick-crypto';

const OFFLINE_LICENSE_ALGORITHM = 'RS256';
const OFFLINE_LICENSE_PUBLIC_KEY = `-----BEGIN PUBLIC KEY-----
REPLACE_WITH_KUBANFY_OFFLINE_LICENSE_PUBLIC_KEY
-----END PUBLIC KEY-----`;

export type OfflineLicenseClaims = {
  sub: string;
  exp: number;
  iat?: number;
  jti: string;
  type: 'offline_license';
  license_id: string;
  device_id: string;
  track_id: string;
  asset_version: number;
  quality: string;
  content_hash: string;
};

function decodeJson(segment: string): Record<string, unknown> {
  return JSON.parse(Buffer.from(segment, 'base64url').toString('utf8')) as Record<string, unknown>;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function verifyOfflineLicense(
  token: string,
  expected: {
    trackId: string;
    quality: string;
    deviceId: string;
    userId: string;
    contentHash?: string;
    publicKeyPem?: string;
    nowMs?: number;
  },
): OfflineLicenseClaims {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('Invalid offline license format');

  const [encodedHeader, encodedPayload, encodedSignature] = parts;
  const header = decodeJson(encodedHeader);
  if (header.alg !== OFFLINE_LICENSE_ALGORITHM || header.typ !== 'JWT') {
    throw new Error('Unsupported offline license algorithm');
  }

  const payload = decodeJson(encodedPayload);
  const claims = payload as Partial<OfflineLicenseClaims>;
  if (
    claims.type !== 'offline_license' ||
    typeof claims.sub !== 'string' ||
    typeof claims.jti !== 'string' ||
    typeof claims.license_id !== 'string' ||
    typeof claims.device_id !== 'string' ||
    typeof claims.track_id !== 'string' ||
    typeof claims.quality !== 'string' ||
    typeof claims.content_hash !== 'string' ||
    !isFiniteNumber(claims.exp) ||
    !isFiniteNumber(claims.asset_version)
  ) {
    throw new Error('Malformed offline license claims');
  }

  const nowMs = expected.nowMs ?? Date.now();
  if (claims.exp * 1000 <= nowMs) throw new Error('Offline license expired');
  if (isFiniteNumber(claims.iat) && claims.iat * 1000 > nowMs + 60_000) {
    throw new Error('Offline license issued in the future');
  }
  if (
    claims.track_id !== expected.trackId ||
    claims.quality !== expected.quality ||
    claims.device_id !== expected.deviceId ||
    claims.sub !== expected.userId
  ) {
    throw new Error('Offline license track binding mismatch');
  }
  if (expected.contentHash && claims.content_hash !== expected.contentHash) {
    throw new Error('Offline license content binding mismatch');
  }

  const publicKeyPem = expected.publicKeyPem || OFFLINE_LICENSE_PUBLIC_KEY;
  if (publicKeyPem.includes('REPLACE_WITH_KUBANFY')) {
    throw new Error('Offline license public key is not configured');
  }

  const verifier = crypto.createVerify('RSA-SHA256');
  verifier.update(encodedHeader + '.' + encodedPayload);
  const valid = verifier.verify(
    {key: publicKeyPem, format: 'pem', type: 'spki'},
    Buffer.from(encodedSignature, 'base64url'),
  );
  if (!valid) throw new Error('Invalid offline license signature');

  return claims as OfflineLicenseClaims;
}

export function getOfflineLicensePublicKey(): string {
  return OFFLINE_LICENSE_PUBLIC_KEY;
}
