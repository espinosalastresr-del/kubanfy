/**
 * KubanFy shell Service Worker (B3).
 * - Precache app shell only.
 * - Network-first for same-origin navigations / assets.
 * - NEVER intercept cross-origin (R2 signed URLs, API hosts).
 * - Does not touch entitlement, audio, or IndexedDB.
 */
const CACHE = "kubanfy-shell-v3";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icon.svg", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png", "/favicon-32.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  let url;
  try {
    url = new URL(request.url);
  } catch {
    return;
  }

  // Never intercept cross-origin (API, R2 signed URLs, CDN audio).
  if (url.origin !== self.location.origin) return;

  // Navigations: network-first, fallback to cached shell.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          void caches.open(CACHE).then((c) => c.put("/index.html", copy)).catch(() => {});
          return response;
        })
        .catch(() =>
          caches.match("/index.html").then((r) => r || caches.match("/") || Response.error()),
        ),
    );
    return;
  }

  // Same-origin static: stale-while-revalidate for shell assets only.
  const path = url.pathname;
  const isShell =
    path === "/" ||
    path === "/index.html" ||
    path === "/manifest.webmanifest" ||
    path === "/icon.svg" ||\n    path === "/icon-192.png" ||\n    path === "/icon-512.png" ||\n    path === "/apple-touch-icon.png" ||\n    path === "/favicon-32.png" ||
    path.endsWith(".css") ||
    path.endsWith(".js") ||
    path.endsWith(".svg") ||
    path.endsWith(".woff2");

  if (!isShell) return;

  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(request);
      const network = fetch(request)
        .then((response) => {
          if (response.ok) void cache.put(request, response.clone()).catch(() => {});
          return response;
        })
        .catch(() => cached);
      return cached || network;
    }),
  );
});
