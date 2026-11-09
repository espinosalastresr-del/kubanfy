import test from "node:test";
import assert from "node:assert/strict";
import { verifyOfflineLicense } from "../src/offlineLicense.ts";

const DEVICE = "browser-device-0123456789";
const TRACK_ID = "8b7e7e7e-1111-4444-8888-123456789abc";
const HASH = "a".repeat(64);
const QUALITY = "low";

function base64url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function pem(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  const base64 = btoa(binary).match(/.{1,64}/g).join("\n");
  return `-----BEGIN PUBLIC KEY-----\n${base64}\n-----END PUBLIC KEY-----`;
}

async function fixture(overrides = {}) {
  const keys = await crypto.subtle.generateKey(
    {
      name: "RSASSA-PKCS1-v1_5",
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: "SHA-256",
    },
    true,
    ["sign", "verify"],
  );
  const publicDer = new Uint8Array(await crypto.subtle.exportKey("spki", keys.publicKey));
  const publicKeyPem = pem(publicDer);
  const nowSeconds = Math.floor(Date.now() / 1000);
  const claims = {
    sub: "user-123",
    iat: nowSeconds - 10,
    exp: nowSeconds + 3600,
    jti: "license-jti-123",
    type: "offline_license",
    license_id: "license-123",
    device_id: DEVICE,
    track_id: TRACK_ID,
    asset_version: 3,
    quality: QUALITY,
    content_hash: HASH,
    ...overrides,
  };
  const headerPart = base64url(new TextEncoder().encode(JSON.stringify({ alg: "RS256", typ: "JWT" })));
  const payloadPart = base64url(new TextEncoder().encode(JSON.stringify(claims)));
  const signingInput = `${headerPart}.${payloadPart}`;
  const signature = new Uint8Array(await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    keys.privateKey,
    new TextEncoder().encode(signingInput),
  ));
  const token = `${signingInput}.${base64url(signature)}`;
  const expiresAt = new Date(claims.exp * 1000).toISOString();
  return {
    token,
    publicKeyPem,
    claims,
    license: {
      token,
      expiresAt,
      quality: QUALITY,
      contentHash: HASH,
      assetVersion: 3,
      deviceId: DEVICE,
      source: "bootstrap",
      publicKeyPem,
    },
    track: {
      trackId: TRACK_ID,
      quality: QUALITY,
      contentHash: HASH,
      assetVersion: 3,
      source: "bootstrap",
    },
  };
}

test("accepts a valid RS256 offline license bound to the current device and asset", async () => {
  const value = await fixture();
  const claims = await verifyOfflineLicense(value.license, value.track, DEVICE);
  assert.equal(claims.type, "offline_license");
  assert.equal(claims.track_id, TRACK_ID);
});

test("rejects a modified JWT signature", async () => {
  const value = await fixture();
  const [header, payload, signature] = value.token.split(".");
  const replacement = signature.endsWith("A") ? "B" : "A";
  const altered = `${header}.${payload}.${signature.slice(0, -1)}${replacement}`;
  await assert.rejects(
    verifyOfflineLicense({ ...value.license, token: altered }, value.track, DEVICE),
    /firma/i,
  );
});

test("rejects expired licenses", async () => {
  const value = await fixture();
  await assert.rejects(
    verifyOfflineLicense(value.license, value.track, DEVICE, Date.parse(value.license.expiresAt) + 1000),
    /vencida|expirada/i,
  );
});

test("rejects a license copied to another browser device", async () => {
  const value = await fixture();
  await assert.rejects(verifyOfflineLicense(value.license, value.track, "other-device"), /dispositivo/i);
});

test("rejects asset hash, version and quality mismatches", async () => {
  const value = await fixture();
  await assert.rejects(
    verifyOfflineLicense(value.license, { ...value.track, contentHash: "b".repeat(64) }, DEVICE),
    /asset|hash/i,
  );
  await assert.rejects(
    verifyOfflineLicense(value.license, { ...value.track, assetVersion: 4 }, DEVICE),
    /asset|versión/i,
  );
  await assert.rejects(
    verifyOfflineLicense(value.license, { ...value.track, quality: "medium" }, DEVICE),
    /quality|calidad/i,
  );
});

test("rejects unsupported JWT algorithms", async () => {
  const value = await fixture();
  const [_, payload, signature] = value.token.split(".");
  const header = base64url(new TextEncoder().encode(JSON.stringify({ alg: "HS256", typ: "JWT" })));
  await assert.rejects(
    verifyOfflineLicense({ ...value.license, token: `${header}.${payload}.${signature}` }, value.track, DEVICE),
    /RS256|algoritmo/i,
  );
});

test("rejects missing public keys and mismatched local license metadata", async () => {
  const value = await fixture();
  await assert.rejects(
    verifyOfflineLicense({ ...value.license, publicKeyPem: undefined }, value.track, DEVICE),
    /clave pública/i,
  );
  await assert.rejects(
    verifyOfflineLicense({ ...value.license, deviceId: "other-device" }, value.track, DEVICE),
    /dispositivo/i,
  );
});
