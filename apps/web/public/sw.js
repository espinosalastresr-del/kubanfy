const CACHE = "kubanfy-shell-v2";
const ASSET_CACHE = "kubanfy-assets-v2";
const SHELL = ["/", "/manifest.webmanifest", "/icon.svg"];
const MAX_ASSETS = 80;

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(async cache => {
        // Cache the shell individually: one missing optional asset must not
        // prevent the app shell from being installed.
        await Promise.all(SHELL.map(async path => {
          try {
            const response = await fetch(path, { cache: "reload" });
            if (response.ok) await cache.put(path, response);
          } catch {
            // A previous installation may already have cached this resource.
          }
        }));
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(key =>
          (key.startsWith("kubanfy-shell-") || key.startsWith("kubanfy-assets-")) &&
          ![CACHE, ASSET_CACHE].includes(key)
        ).map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

function isStaticAsset(url) {
  return url.pathname.startsWith("/assets/") ||
    /\.(?:css|js|mjs|svg|png|jpg|jpeg|webp|avif|woff2?)$/i.test(url.pathname);
}

async function trimAssetCache(cache) {
  const keys = await cache.keys();
  if (keys.length > MAX_ASSETS) {
    await Promise.all(keys.slice(0, keys.length - MAX_ASSETS).map(key => cache.delete(key)));
  }
}

async function networkFirstNavigation(request) {
  const shell = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) {
      // Store only the app entry point, never arbitrary navigations or
      // user-specific/API responses.
      if (new URL(request.url).pathname === "/") {
        await shell.put("/", response.clone());
      }
      return response;
    }
    throw new Error("Navigation request failed");
  } catch {
    return (await shell.match("/")) ||
      new Response("KubanFy no está disponible sin conexión. Vuelve a intentarlo cuando tengas red.", {
        status: 503,
        headers: { "Content-Type": "text/plain; charset=utf-8" }
      });
  }
}

async function networkFirstAsset(request) {
  const cache = await caches.open(ASSET_CACHE);
  try {
    const response = await fetch(request);
    if (response.ok && response.type !== "opaque") {
      await cache.put(request, response.clone());
      await trimAssetCache(cache);
    }
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw new Error("Static asset unavailable offline");
  }
}

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Never cache API traffic, authenticated content, or audio streams.
  if (url.pathname.startsWith("/api/") ||
      url.pathname.startsWith("/v1/") ||
      request.headers.has("authorization") ||
      request.destination === "audio" ||
      request.destination === "video") return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request));
    return;
  }

  if (isStaticAsset(url) && !url.search) {
    event.respondWith(networkFirstAsset(request));
  }
});
