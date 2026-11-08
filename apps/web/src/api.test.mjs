import assert from "node:assert/strict";
import test from "node:test";

class MemoryStorage {
  values = new Map();
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

const localStorage = new MemoryStorage();
const sessionStorage = new MemoryStorage();
sessionStorage.setItem("kubanfy.refresh", "legacy-refresh-token");
sessionStorage.setItem("kubanfy.device", "device-identifier-123456");
localStorage.setItem("kubanfy.device", "device-identifier-123456");

globalThis.window = {
  localStorage,
  sessionStorage,
  location: { protocol: "https:", origin: "https://kubanfy.example" },
  setTimeout,
};
globalThis.document = { cookie: "" };

const api = await import("./api.ts");

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("module initialization removes only the legacy refresh key", () => {
  assert.equal(sessionStorage.getItem("kubanfy.refresh"), null);
  assert.equal(sessionStorage.getItem("kubanfy.device"), "device-identifier-123456");
  assert.equal(localStorage.getItem("kubanfy.device"), "device-identifier-123456");
});

test("login uses same-origin credentials and never persists a refresh token", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    return jsonResponse({
      user: { id: "user-1" },
      tokens: { access_token: "access-1", token_type: "bearer", expires_in: 900 },
    });
  };

  await api.login("ray@example.com", "correct-password");
  assert.equal(calls[0].url, "/api/v1/auth/login");
  assert.equal(calls[0].init.credentials, "same-origin");
  assert.equal(sessionStorage.getItem("kubanfy.refresh"), null);
  assert.equal(JSON.stringify(calls[0].init.body).includes("refresh_token"), false);
});

test("restoreSession refreshes through the HttpOnly cookie and stores only access in memory", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    if (String(url) === "/api/v1/auth/refresh") {
      return jsonResponse({ access_token: "restored-access", token_type: "bearer", expires_in: 900 });
    }
    return jsonResponse({ id: "user-1" });
  };

  assert.equal(await api.restoreSession(), true);
  assert.equal(calls[0].url, "/api/v1/auth/refresh");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.credentials, "same-origin");
  assert.equal(calls[0].init.body, undefined);
  await api.me();
  assert.equal(calls[1].init.headers.get("authorization"), "Bearer restored-access");
});

test("simultaneous 401 responses share one cookie refresh and retry once", async () => {
  api.setTokens({ access_token: "expired-access", token_type: "bearer", expires_in: 1 });
  let refreshCalls = 0;
  let initialCalls = 0;
  let releaseRefresh;
  const refreshGate = new Promise((resolve) => { releaseRefresh = resolve; });

  globalThis.fetch = async (url, init) => {
    const target = String(url);
    if (target === "/api/v1/auth/refresh") {
      refreshCalls += 1;
      await refreshGate;
      return jsonResponse({ access_token: "fresh-access", token_type: "bearer", expires_in: 900 });
    }
    if (init.headers.get("authorization") === "Bearer expired-access") {
      initialCalls += 1;
      return jsonResponse({ detail: "expired" }, 401);
    }
    return jsonResponse({ id: "user-1" });
  };

  const first = api.me();
  const second = api.me();
  while (initialCalls < 2) await new Promise((resolve) => setImmediate(resolve));
  releaseRefresh();
  await Promise.all([first, second]);
  assert.equal(refreshCalls, 1);
  assert.equal(initialCalls, 2);
});

test("definitive refresh 401 clears the access token", async () => {
  api.setTokens({ access_token: "expired-access", token_type: "bearer", expires_in: 1 });
  let subsequentAuthorization;
  globalThis.fetch = async (url, init) => {
    if (String(url) === "/api/v1/auth/refresh") return jsonResponse({ detail: "invalid session" }, 401);
    if (!subsequentAuthorization) {
      subsequentAuthorization = init.headers.get("authorization");
      return jsonResponse({ detail: "expired" }, 401);
    }
    subsequentAuthorization = init.headers.get("authorization");
    return jsonResponse({ id: "guest" });
  };

  await assert.rejects(api.me(), (error) => error.status === 401);
  await api.me();
  assert.equal(subsequentAuthorization, null);
});

test("transient refresh 503 preserves the in-memory access token", async () => {
  api.setTokens({ access_token: "still-valid-access", token_type: "bearer", expires_in: 900 });
  let nextAuthorization;
  globalThis.fetch = async (url, init) => {
    if (String(url) === "/api/v1/auth/refresh") return jsonResponse({ detail: "temporarily unavailable" }, 503);
    if (!nextAuthorization) return jsonResponse({ detail: "expired" }, 401);
    return jsonResponse({ id: "user-1" });
  };

  await assert.rejects(api.me(), (error) => error.status === 503);
  globalThis.fetch = async (_url, init) => {
    nextAuthorization = init.headers.get("authorization");
    return jsonResponse({ id: "user-1" });
  };
  await api.me();
  assert.equal(nextAuthorization, "Bearer still-valid-access");
});

test("network failure during refresh preserves the in-memory access token", async () => {
  api.setTokens({ access_token: "still-valid-access", token_type: "bearer", expires_in: 900 });
  let initial = true;
  globalThis.fetch = async (url) => {
    if (String(url) === "/api/v1/auth/refresh") throw new TypeError("offline");
    if (initial) { initial = false; return jsonResponse({ detail: "expired" }, 401); }
    return jsonResponse({ id: "user-1" });
  };

  await assert.rejects(api.me(), /offline/);
  let authorization;
  globalThis.fetch = async (_url, init) => {
    authorization = init.headers.get("authorization");
    return jsonResponse({ id: "user-1" });
  };
  await api.me();
  assert.equal(authorization, "Bearer still-valid-access");
});

test("logout calls the same-origin endpoint and clears access state after it settles", async () => {
  api.setTokens({ access_token: "access-before-logout", token_type: "bearer", expires_in: 900 });
  let logoutCall;
  globalThis.fetch = async (url, init) => {
    logoutCall = { url: String(url), init };
    return new Response(null, { status: 204 });
  };

  await api.logout();
  assert.equal(logoutCall.url, "/api/v1/auth/logout");
  assert.equal(logoutCall.init.method, "POST");
  assert.equal(logoutCall.init.credentials, "same-origin");

  let authorization;
  globalThis.fetch = async (_url, init) => {
    authorization = init.headers.get("authorization");
    return jsonResponse({ id: "guest" });
  };
  await api.me();
  assert.equal(authorization, null);
});
