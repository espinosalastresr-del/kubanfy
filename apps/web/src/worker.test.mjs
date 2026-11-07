import assert from "node:assert/strict";
import test from "node:test";

import { proxyApiRequest, handleRequest } from "./worker.ts";

const API_ORIGIN = "https://kubanfy-api-staging.globumlatinmusic.workers.dev";

test("proxy fixes upstream, strips /api, and preserves query, method, headers and body stream", async () => {
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("payload"));
      controller.close();
    },
  });
  const request = new Request("https://web.example/api/v1/auth/refresh?source=web&x=1", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      cookie: "kubanfy_refresh=secret",
      authorization: "Bearer access",
      "x-kubanfy-platform": "web",
    },
    body,
    duplex: "half",
  });
  let observedUrl;
  let observedInit;
  const upstreamResponse = new Response("upstream", {
    status: 201,
    headers: {
      "content-type": "application/json",
      "set-cookie": "kubanfy_refresh=rotated; Path=/api/v1/auth; HttpOnly; Secure; SameSite=Lax",
      "x-request-id": "request-123",
    },
  });

  const response = await proxyApiRequest(
    request,
    { API_ORIGIN },
    async (url, init) => {
      observedUrl = String(url);
      observedInit = init;
      return upstreamResponse;
    },
  );

  assert.equal(observedUrl, `${API_ORIGIN}/v1/auth/refresh?source=web&x=1`);
  assert.equal(observedInit.method, "POST");
  assert.equal(observedInit.body, body);
  assert.equal(observedInit.headers.get("cookie"), "kubanfy_refresh=secret");
  assert.equal(observedInit.headers.get("authorization"), "Bearer access");
  assert.equal(observedInit.headers.get("x-kubanfy-platform"), "web");
  assert.equal(response.status, 201);
  assert.equal(response.headers.get("set-cookie"), upstreamResponse.headers.get("set-cookie"));
  assert.equal(response.headers.get("x-request-id"), "request-123");
});

test("proxy removes hop-by-hop and caller-controlled forwarding headers", async () => {
  const request = new Request("https://web.example/api/v1/ping", {
    headers: {
      connection: "keep-alive, x-remove-me",
      "keep-alive": "timeout=5",
      "x-remove-me": "secret",
      "x-forwarded-host": "evil.example",
      "x-forwarded-proto": "http",
      forwarded: "for=127.0.0.1",
      "x-kubanfy-internal-user": "admin",
      "x-request-id": "client-id",
    },
  });
  let forwardedHeaders;
  await proxyApiRequest(request, { API_ORIGIN }, async (_url, init) => {
    forwardedHeaders = init.headers;
    return new Response("ok");
  });

  for (const name of [
    "connection", "keep-alive", "x-remove-me", "x-forwarded-host",
    "x-forwarded-proto", "forwarded", "x-kubanfy-internal-user",
  ]) {
    assert.equal(forwardedHeaders.has(name), false, name);
  }
  assert.equal(forwardedHeaders.get("x-request-id"), "client-id");
});

test("proxy rejects API_ORIGIN values that are not HTTPS origins", async () => {
  const request = new Request("https://web.example/api/v1/ping");
  for (const API_ORIGIN of [
    "http://api.example",
    "https://user:pass@api.example",
    "https://api.example/v1",
    "https://api.example?target=evil",
    "https://api.example#fragment",
  ]) {
    await assert.rejects(
      proxyApiRequest(request, { API_ORIGIN }, async () => new Response("unexpected")),
      /API_ORIGIN/,
    );
  }
});

test("non-API requests are delegated to the static assets binding", async () => {
  const request = new Request("https://web.example/library");
  let assetRequest;
  const response = await handleRequest(
    request,
    {
      API_ORIGIN,
      ASSETS: {
        fetch: async (received) => {
          assetRequest = received;
          return new Response("spa shell", { headers: { "content-type": "text/html" } });
        },
      },
    },
    async () => new Response("must not proxy", { status: 500 }),
  );

  assert.equal(assetRequest, request);
  assert.equal(await response.text(), "spa shell");
});

test("paths outside /api/ never reach the API proxy", async () => {
  const request = new Request("https://web.example/api");
  let proxyCalled = false;
  const response = await handleRequest(
    request,
    {
      API_ORIGIN,
      ASSETS: { fetch: async () => new Response("asset", { status: 200 }) },
    },
    async () => {
      proxyCalled = true;
      return new Response("unexpected");
    },
  );

  assert.equal(proxyCalled, false);
  assert.equal(await response.text(), "asset");
});
