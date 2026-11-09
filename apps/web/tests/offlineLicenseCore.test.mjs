import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { verifyOfflineLicenseToken } from "../src/offlineLicenseCore.ts";

Object.defineProperty(globalThis, "crypto", { value: webcrypto, configurable: true });

const expected = {
  userId: "user-1", deviceId: "device-1", trackId: "track-1",
  quality: "medium", contentHash: "sha256:asset-hash", assetVersion: 3,
};
function b64url(bytes) { return Buffer.from(bytes).toString("base64url"); }

async function makeKeyPair() {
  const pair = await crypto.subtle.generateKey({
    name: "RSASSA-PKCS1-v1_5", modulusLength: 2048,
    publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256",
  }, true, ["sign", "verify"]);
  const spki = new Uint8Array(await crypto.subtle.exportKey("spki", pair.publicKey));
  const pemBody = Buffer.from(spki).toString("base64").match(/.{1,64}/g).join("\n");
  return { privateKey: pair.privateKey, publicKey: `-----BEGIN PUBLIC KEY-----\n${pemBody}\n-----END PUBLIC KEY-----` };
}

async function signLicense(privateKey, overrides = {}, headerOverrides = {}) {
  const now = Math.floor(Date.now() / 1000);
  const claims = {
    sub: expected.userId, iat: now, exp: now + 3600, jti: "jti-1",
    type: "offline_license", license_id: "license-1", device_id: expected.deviceId,
    track_id: expected.trackId, asset_version: expected.assetVersion,
    quality: expected.quality, content_hash: expected.contentHash, ...overrides,
  };
  const header = { alg: "RS256", typ: "JWT", ...headerOverrides };
  const encodedHeader = b64url(Buffer.from(JSON.stringify(header)));
  const encodedClaims = b64url(Buffer.from(JSON.stringify(claims)));
  const input = `${encodedHeader}.${encodedClaims}`;
  const signature = await crypto.subtle.sign(
    { name: "RSASSA-PKCS1-v1_5" }, privateKey, new TextEncoder().encode(input),
  );
  return { token: `${input}.${b64url(signature)}`, claims };
}

test("accepts a correctly signed license bound to the user, device and asset", async () => {
  const pair = await makeKeyPair();
  const { token, claims } = await signLicense(pair.privateKey);
  await assert.doesNotReject(verifyOfflineLicenseToken(token, {
    ...expected, expiresAt: new Date(claims.exp * 1000).toISOString(),
  }, [{ algorithm: "RS256", key_id: "test-key", public_key: pair.publicKey }]));
});

test("rejects a license signed by a different public key", async () => {
  const signer = await makeKeyPair();
  const wrong = await makeKeyPair();
  const { token, claims } = await signLicense(signer.privateKey);
  await assert.rejects(verifyOfflineLicenseToken(token, {
    ...expected, expiresAt: new Date(claims.exp * 1000).toISOString(),
  }, [{ algorithm: "RS256", key_id: "wrong", public_key: wrong.publicKey }]), /firma/);
});

test("rejects a license bound to another browser device", async () => {
  const pair = await makeKeyPair();
  const { token, claims } = await signLicense(pair.privateKey);
  await assert.rejects(verifyOfflineLicenseToken(token, {
    ...expected, deviceId: "different-device", expiresAt: new Date(claims.exp * 1000).toISOString(),
  }, [{ algorithm: "RS256", key_id: "test", public_key: pair.publicKey }]), /no corresponde/);
});

test("rejects expired licenses even when their signature is valid", async () => {
  const pair = await makeKeyPair();
  const { token, claims } = await signLicense(pair.privateKey, { exp: Math.floor(Date.now() / 1000) - 1 });
  await assert.rejects(verifyOfflineLicenseToken(token, {
    ...expected, expiresAt: new Date(claims.exp * 1000).toISOString(),
  }, [{ algorithm: "RS256", key_id: "test", public_key: pair.publicKey }]), /vencido/);
});

test("rejects an algorithm downgrade", async () => {
  const pair = await makeKeyPair();
  const { token, claims } = await signLicense(pair.privateKey, {}, { alg: "none" });
  await assert.rejects(verifyOfflineLicenseToken(token, {
    ...expected, expiresAt: new Date(claims.exp * 1000).toISOString(),
  }, [{ algorithm: "RS256", key_id: "test", public_key: pair.publicKey }]), /algoritmo/);
});

test("rejects a local expiry value that differs from the signed token", async () => {
  const pair = await makeKeyPair();
  const { token } = await signLicense(pair.privateKey);
  await assert.rejects(verifyOfflineLicenseToken(token, {
    ...expected, expiresAt: new Date(Date.now() + 86_400_000).toISOString(),
  }, [{ algorithm: "RS256", key_id: "test", public_key: pair.publicKey }]), /expiración/);
});
