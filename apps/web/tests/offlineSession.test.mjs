import test from "node:test";
import assert from "node:assert/strict";
import {
  clearOfflineSessionSnapshot,
  readOfflineSessionSnapshot,
  saveOfflineSessionSnapshot,
} from "../src/offlineSession.ts";

const storage = new Map();
globalThis.window = {
  localStorage: {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: (key) => storage.delete(key),
  },
};

test("stores a minimal offline profile without authentication tokens", () => {
  saveOfflineSessionSnapshot({
    id: "user-1",
    email: "ray@example.test",
    display_name: "Ray",
    avatar: null,
    country: "CU",
    language: "es",
    status: "active",
    email_verified: true,
    access_token: "must-not-be-stored",
  }, "premium");

  const raw = storage.get("kubanfy.offline-session.v1");
  assert.ok(raw);
  assert.equal(raw.includes("must-not-be-stored"), false);
  const snapshot = readOfflineSessionSnapshot();
  assert.equal(snapshot.user.id, "user-1");
  assert.equal(snapshot.planTier, "premium");
});

test("rejects stale or inactive account snapshots", () => {
  storage.set("kubanfy.offline-session.v1", JSON.stringify({
    user: { id: "user-2", display_name: "Inactive", status: "disabled" },
    planTier: "free",
    savedAt: Date.now(),
  }));
  assert.equal(readOfflineSessionSnapshot(), null);

  storage.set("kubanfy.offline-session.v1", JSON.stringify({
    user: { id: "user-2", display_name: "Old", status: "active" },
    planTier: "free",
    savedAt: Date.now() - 31 * 24 * 60 * 60 * 1000,
  }));
  assert.equal(readOfflineSessionSnapshot(), null);
});

test("clears the offline account snapshot on logout", () => {
  saveOfflineSessionSnapshot({ id: "user-3", display_name: "User", status: "active" }, "free");
  clearOfflineSessionSnapshot();
  assert.equal(readOfflineSessionSnapshot(), null);
});
