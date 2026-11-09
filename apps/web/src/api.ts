export type Track = {
  id: string;
  title: string;
  duration: number | null;
  artwork_url?: string | null;
  artists: { id: string; name: string; slug: string; verified: boolean }[];
};

export type SearchResult = {
  provider: string;
  provider_track_id: string;
  track_id: string | null;
  title: string;
  artists: string[];
  album?: string | null;
  duration?: number | null;
  artwork?: string | null;
};

type Tokens = { access_token: string; refresh_token: string; expires_in: number };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code = "HTTP_ERROR",
    public details: Record<string, unknown> = {},
    public requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const API = (import.meta.env.VITE_API_BASE_URL || "https://kubanfy-api-staging.globumlatinmusic.workers.dev").replace(/\/+$/, "");
let accessToken: string | null = null;
function readSessionValue(key: string): string | null {
  try { return window.sessionStorage.getItem(key); } catch { return null; }
}
function writeSessionValue(key: string, value: string | null): void {
  try {
    if (value === null) window.sessionStorage.removeItem(key);
    else window.sessionStorage.setItem(key, value);
  } catch {
    // Storage can be unavailable in private/restricted browser contexts.
  }
}
let refreshToken: string | null = readSessionValue("kubanfy.refresh");
let refreshInFlight: Promise<boolean> | null = null;
let tokenVersion = 0;
let fallbackDeviceId: string | null = null;


async function postChallenge<T>(path: string, body: Record<string, string>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar para verificar la identidad del navegador.", "NETWORK_ERROR");
  }
  if (!response.ok) {
    let message = response.statusText || "No se pudo verificar el dispositivo.";
    let code = "DEVICE_PROOF_ERROR";
    try {
      const payload = await response.json();
      message = payload?.error?.message || payload?.detail || message;
      code = payload?.error?.code || code;
    } catch {}
    throw new ApiError(response.status, message, code);
  }
  return response.json() as Promise<T>;
}

export function createLoginChallenge(deviceId: string, publicKey: string) {
  return postChallenge<DeviceChallenge>("/v1/auth/devices/login-challenge", { device_id: deviceId, public_key: publicKey });
}

export function createRefreshChallenge(refreshTokenValue: string, deviceId: string) {
  return postChallenge<DeviceChallenge>("/v1/auth/refresh/challenge", { refresh_token: refreshTokenValue, device_id: deviceId });
}

export function setTokens(tokens: Tokens) {
  tokenVersion += 1;
  refreshInFlight = null;
  accessToken = tokens.access_token;
  refreshToken = tokens.refresh_token;
  writeSessionValue("kubanfy.refresh", refreshToken);
}

export function clearTokens() {
  tokenVersion += 1;
  refreshInFlight = null;
  accessToken = null;
  refreshToken = null;
  writeSessionValue("kubanfy.refresh", null);
}

async function refreshSessionToken(deviceId: string): Promise<boolean> {
  if (!refreshToken) return false;
  if (refreshInFlight) return refreshInFlight;

  const tokenBeingRefreshed = refreshToken;
  const startingVersion = tokenVersion;
  const operation = (async (): Promise<boolean> => {
    let proof: { challenge_id: string; signature: string };
    try {
      const identity = await import("./deviceIdentity");
      proof = await identity.createRefreshProof(tokenBeingRefreshed, deviceId);
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) clearTokens();
      return false;
    }

    let response: Response;
    try {
      response = await fetch(`${API}/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          refresh_token: tokenBeingRefreshed, device_id: deviceId,
          challenge_id: proof.challenge_id, signature: proof.signature,
        }),
      });
    } catch {
      // Preserve the refresh token during transient/offline failures.
      return tokenVersion !== startingVersion && Boolean(accessToken && refreshToken);
    }

    // A concurrent login/logout may have changed the credentials while this
    // request was in flight. Never let a late response overwrite that choice.
    if (tokenVersion !== startingVersion || refreshToken !== tokenBeingRefreshed) {
      return Boolean(accessToken && refreshToken);
    }

    if (!response.ok) {
      // Only definitive authentication failures invalidate local credentials.
      if (response.status === 401 || response.status === 403) clearTokens();
      return false;
    }

    try {
      const body = await response.json() as Tokens;
      if (
        typeof body?.access_token !== "string" ||
        typeof body?.refresh_token !== "string"
      ) return false;
      if (tokenVersion !== startingVersion || refreshToken !== tokenBeingRefreshed) {
        return Boolean(accessToken && refreshToken);
      }
      setTokens(body);
      return true;
    } catch {
      return false;
    }
  })();

  refreshInFlight = operation;
  try {
    return await operation;
  } finally {
    if (refreshInFlight === operation) refreshInFlight = null;
  }
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const requestAccessToken = accessToken;
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("X-KubanFy-Platform", "web");
  const device = getDeviceId();
  headers.set("X-Device-ID", device);
  if (requestAccessToken) headers.set("Authorization", `Bearer ${requestAccessToken}`);
  const requestUrl = `${API}${path}`;
  const method = (init.method || "GET").toUpperCase();
  let response: Response;
  try {
    response = await fetch(requestUrl, { ...init, headers });
  } catch (error) {
    // Cancellation is final; do not schedule a retry after the user stops a download.
    if (init.signal?.aborted) throw error;
    // Retry only safe reads. Never replay login, writes, or other POST requests.
    if (method !== "GET") throw error;
    await new Promise((resolve) => window.setTimeout(resolve, 350));
    if (init.signal?.aborted) throw error;
    response = await fetch(requestUrl, { ...init, headers });
  }
  if (init.signal?.aborted) {
    throw init.signal.reason instanceof Error
      ? init.signal.reason
      : new DOMException("Solicitud cancelada", "AbortError");
  }
  if (response.status === 401 && retry) {
    // Another concurrent request may already have rotated the token pair.
    if (accessToken && accessToken !== requestAccessToken) {
      return request<T>(path, init, false);
    }
    if (await refreshSessionToken(device)) {
      return request<T>(path, init, false);
    }
  }
  if (!response.ok) {
    let detail = response.statusText;
    let code = "HTTP_ERROR";
    let details: Record<string, unknown> = {};
    try {
      const body = await response.json();
      const error = body?.error;
      detail = error?.message || body?.detail || detail;
      code = error?.code || code;
      details = error?.details || {};
    } catch {}
    throw new ApiError(
      response.status,
      detail,
      code,
      details,
      response.headers.get("X-Request-ID") || undefined,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

function createDeviceId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
      const bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
    }
  } catch {
    // Fall through to a non-secret, per-browser identifier.
  }
  return `kf-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

const DEVICE_COOKIE = "kubanfy_device";
function readDeviceCookie(): string | null {
  try {
    const entry = document.cookie.split("; ").find((part) => part.startsWith(DEVICE_COOKIE + "="));
    return entry ? decodeURIComponent(entry.slice(DEVICE_COOKIE.length + 1)) : null;
  } catch { return null; }
}
function persistDeviceCookie(value: string): void {
  try {
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${DEVICE_COOKIE}=${encodeURIComponent(value)}; Max-Age=31536000; Path=/; SameSite=Lax${secure}`;
  } catch {}
}

export function getDeviceId(): string {
  try {
    const stored = window.localStorage.getItem("kubanfy.device");
    if (stored) { persistDeviceCookie(stored); return stored; }
  } catch {}
  try {
    const stored = window.sessionStorage.getItem("kubanfy.device");
    if (stored) { persistDeviceCookie(stored); return stored; }
  } catch {}
  const cookie = readDeviceCookie();
  if (cookie && /^[a-zA-Z0-9-]{16,128}$/.test(cookie)) {
    try { window.localStorage.setItem("kubanfy.device", cookie); } catch {}
    try { window.sessionStorage.setItem("kubanfy.device", cookie); } catch {}
    fallbackDeviceId = cookie;
    return cookie;
  }
  if (!fallbackDeviceId) fallbackDeviceId = createDeviceId();
  try { window.localStorage.setItem("kubanfy.device", fallbackDeviceId); } catch {}
  try { window.sessionStorage.setItem("kubanfy.device", fallbackDeviceId); } catch {}
  persistDeviceCookie(fallbackDeviceId);
  return fallbackDeviceId;
}

export async function register(email: string, password: string, displayName: string) {
  return request<{ id: string; email: string; display_name: string; status: string; email_verified: boolean }>("/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, display_name: displayName, language: "es" }),
  }, false);
}

export async function requestEmailVerification(email: string) {
  return request<{ message: string }>("/v1/auth/email-verification/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim().toLowerCase() }),
  }, false);
}

export async function confirmEmailVerification(token: string) {
  return request<{ message: string }>("/v1/auth/email-verification/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  }, false);
}

export async function login(email: string, password: string) {
  const deviceId = getDeviceId();
  const identity = await import("./deviceIdentity");
  const proof = await identity.createLoginProof(deviceId);
  const body = await request<{ user: unknown; tokens: Tokens }>("/v1/auth/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email, password, device_id: deviceId, device_name: "KubanFy Web", platform: "web", ...proof,
    }),
  }, false);
  setTokens(body.tokens);
  return body.user;
}

export type DiscoveryHome = {
  country: string;
  local_artists: { id: string; name: string; slug: string; verified: boolean }[];
  top_50_country: { rank: number; track_id: string; title: string | null; score: number; metrics: Record<string, number> }[];
  top_50_global: { rank: number; track_id: string; title: string | null; score: number; metrics: Record<string, number> }[];
  new_releases: { id: string; title: string; duration: number | null }[];
  trending: { rank: number; track_id: string; title: string | null; score: number; metrics: Record<string, number> }[];
  viral_by_country: { rank: number; track_id: string; title: string | null; score: number; metrics: Record<string, number> }[];
};

export async function discoveryHome() {
  return request<DiscoveryHome>("/v1/discovery/home");
}

export async function me() { return request<unknown>("/v1/auth/me"); }
export async function searchTracks(q: string) { return request<SearchResult[]>(`/v1/music/search?q=${encodeURIComponent(q)}&limit=20`); }

export async function playback(trackId: string, quality: "low" | "medium") {
  return request<{
    url: string; expires_in_seconds: number; quality: string; track_id: string;
    content_hash: string; kby_key: string; kby_version: number;
    content_type: string | null; streaming_format: string | null; asset_version: number | null;
  }>(`/v1/music/play/${trackId}?quality=${quality}&kby_version=2`);
}

export async function startPlayback(trackId: string, quality: string) {
  return request<{ playback_token: string; playback_session_id: string; heartbeat_interval_seconds: number; qualifying_listen_seconds: number; asset_version: number; content_hash: string }>("/v1/analytics/playback/start", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track_id: trackId, quality }),
  });
}

export async function heartbeat(token: string, positionSeconds: number, paused: boolean) {
  return request<{ qualified: boolean; listened_ms: number; suspicious_score: number }>("/v1/analytics/playback/heartbeat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      token,
      position_ms: Math.max(0, Math.round(positionSeconds * 1000)),
      paused,
    }),
  });
}

export type Favorite = { id: string; target_type: "track" | "artist" | "release"; target_id: string; created_at: string };
export type Playlist = { id: string; name: string; description: string | null; visibility: "private" | "public"; created_at: string; updated_at: string };

export async function listFavorites() {
  return request<Favorite[]>("/v1/favorites");
}
export async function addFavorite(targetId: string) {
  return request<Favorite>("/v1/favorites", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_type: "track", target_id: targetId }),
  });
}
export async function removeFavorite(targetId: string) {
  return request<void>(`/v1/favorites/track/${targetId}`, { method: "DELETE" });
}
export async function listPlaylists() {
  return request<Playlist[]>("/v1/playlists");
}
export async function createPlaylist(name: string) {
  return request<Playlist>("/v1/playlists", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, visibility: "private" }),
  });
}
export async function getPlaylist(id: string) { return request<Playlist>(`/v1/playlists/${id}`); }
export async function renamePlaylist(id: string, name: string, visibility?: "private" | "public") {
  return request<Playlist>(`/v1/playlists/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, ...(visibility ? { visibility } : {}) }) });
}
export async function reorderPlaylistTracks(id: string, trackIds: string[]) {
  return request<{ track_id: string; position: number; added_at: string }[]>(`/v1/playlists/${id}/tracks/order`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ track_ids: trackIds }),
  });
}
export async function listPlaylistTracks(id: string) {
  return request<{ track_id: string; position: number; added_at: string }[]>(`/v1/playlists/${id}/tracks`);
}
export async function getTrackDetail(id: string) { return request<Track>(`/v1/music/tracks/${id}`); }
export async function removeTrackFromPlaylist(playlistId: string, trackId: string) {
  return request<void>(`/v1/playlists/${playlistId}/tracks/${trackId}`, { method: "DELETE" });
}
export async function deletePlaylist(id: string) {
  return request<void>(`/v1/playlists/${id}`, { method: "DELETE" });
}
export async function addTrackToPlaylist(playlistId: string, trackId: string) {
  return request<void>(`/v1/playlists/${playlistId}/tracks/${trackId}`, { method: "POST" });
}

export type MusicDownloadResult = {
  url: string | null;
  expires_in_seconds: number | null;
  quality: string;
  from_cache: boolean;
  track_id: string | null;
  storage_key?: string | null;
  content_hash: string | null;
  kby_key: string | null;
  size_bytes?: number | null;
  download_ticket?: string | null;
  offline_license?: string | null;
  offline_license_expires_at?: string | null;
  asset_version?: number | null;
};

export type OfflineBootstrapItem = {
  track_id: string;
  title: string;
  duration: number | null;
  url: string;
  expires_in_seconds: number;
  quality: string;
  content_hash: string;
  kby_key: string;
  asset_version: number;
  offline_license: string;
  offline_license_expires_at: string;
};

export type OfflineLicenseValidation = {
  license_id: string;
  track_id: string;
  device_id: string;
  quality: string;
  content_hash: string;
  asset_version: number;
  expires_at: string;
};

export async function downloadTrack(
  trackId: string,
  quality: "low" | "medium" | "lossless" = "medium",
  signal?: AbortSignal,
) {
  return request<MusicDownloadResult>("/v1/music/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track_id: trackId, quality, device_id: getDeviceId() }),
    signal,
  });
}

export async function offlineBootstrap(limit = 3, signal?: AbortSignal) {
  const q = Math.min(3, Math.max(1, limit));
  return request<OfflineBootstrapItem[]>(`/v1/music/offline/bootstrap?limit=${q}`, { signal });
}

export async function validateOfflineLicense(token: string) {
  return request<OfflineLicenseValidation>("/v1/offline/licenses/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, device_id: getDeviceId() }),
  });
}

export async function completeDownloadTicket(ticket: string, sizeBytes?: number) {
  return request<{ qualified: boolean }>("/v1/analytics/downloads/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticket, size_bytes: sizeBytes ?? null, device_id: getDeviceId() }),
  });
}

export async function requestPasswordReset(email: string) {
  return request<{ detail?: string }>("/v1/auth/password-reset/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim().toLowerCase() }),
  }, false);
}

export async function confirmPasswordReset(token: string, newPassword: string) {
  return request<{ detail?: string }>("/v1/auth/password-reset/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  }, false);
}

export type UserProfile = {
  id: string;
  email: string;
  display_name: string;
  avatar: string | null;
  country: string;
  language: string;
  status: string;
  email_verified: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type AuthDevice = {
  id: string;
  device_id: string;
  name: string | null;
  platform: string | null;
  os_version: string | null;
  app_version: string | null;
  status: string;
  identity_verified: boolean;
  created_at: string;
  last_seen_at: string;
};

export type AuthSession = {
  id: string;
  status: string;
  ip_country: string | null;
  created_at: string;
  last_activity_at: string;
  expires_at: string;
};

export async function updateProfile(body: {
  display_name: string;
  country: string;
  language: string;
}) {
  return request<UserProfile>("/v1/auth/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function listDevices() {
  return request<AuthDevice[]>("/v1/auth/devices");
}

export type DeviceChallenge = {
  challenge_id: string;
  nonce: string;
  message: string;
  algorithm: "Ed25519";
  expires_in: number;
};

export async function createDeviceChallenge(deviceId: string, publicKey: string) {
  return request<DeviceChallenge>("/v1/auth/devices/challenge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId, public_key: publicKey }),
  });
}

export async function verifyDeviceChallenge(challengeId: string, signature: string) {
  return request<{ id: string; device_id: string; identity_verified: boolean }>(
    "/v1/auth/devices/verify",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ challenge_id: challengeId, signature }),
    },
  );
}

export type UserPreferences = {
  audio_quality: "auto" | "low" | "medium" | "high";
  data_saver: boolean;
  wifi_only_downloads: boolean;
  theme: "system" | "light" | "dark";
  local_content_enabled: boolean;
};

export async function getUserPreferences() {
  return request<UserPreferences>("/v1/preferences");
}

export async function updateUserPreferences(patch: Partial<UserPreferences>) {
  return request<UserPreferences>("/v1/preferences", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export async function revokeDevice(deviceId: string) {
  return request<void>(`/v1/auth/devices/${deviceId}`, { method: "DELETE" });
}

export async function listSessions() {
  return request<AuthSession[]>("/v1/auth/sessions");
}

export async function revokeSession(sessionId: string) {
  return request<void>(`/v1/auth/sessions/${sessionId}`, { method: "DELETE" });
}

export async function logoutAll() {
  return request<void>("/v1/auth/logout-all", { method: "POST" });
}

export type EntitlementItem = {
  id: string;
  scope_type: string;
  scope_id: string | null;
  source: string;
  status: string;
  starts_at: string;
  expires_at: string | null;
  created_at: string;
};

export async function listMyEntitlements() {
  return request<EntitlementItem[]>("/v1/entitlements/me");
}
