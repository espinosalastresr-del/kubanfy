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

const API = import.meta.env.VITE_API_BASE_URL || "https://kubanfy-api-staging.onrender.com";
let accessToken: string | null = null;
let refreshToken: string | null = sessionStorage.getItem("kubanfy.refresh");

export function setTokens(tokens: Tokens) {
  accessToken = tokens.access_token;
  refreshToken = tokens.refresh_token;
  sessionStorage.setItem("kubanfy.refresh", refreshToken);
}

export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  sessionStorage.removeItem("kubanfy.refresh");
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("X-KubanFy-Platform", "web");
  const device = getDeviceId();
  headers.set("X-Device-ID", device);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${API}${path}`, { ...init, headers });
  if (response.status === 401 && retry && refreshToken) {
    const refreshed = await fetch(`${API}/v1/auth/refresh`, {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken, device_id: device }),
    });
    if (refreshed.ok) {
      const body = await refreshed.json();
      setTokens(body);
      return request<T>(path, init, false);
    }
    clearTokens();
  }
  if (!response.ok) {
    let detail = response.statusText;
    try { const body = await response.json(); detail = body.detail || detail; } catch {}
    throw new Error(detail);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function getDeviceId() {
  let id = localStorage.getItem("kubanfy.device");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("kubanfy.device", id);
  }
  return id;
}

export async function register(email: string, password: string, displayName: string) {
  return request<{ id: string; email: string; display_name: string; status: string; email_verified: boolean }>("/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, display_name: displayName, language: "es" }),
  }, false);
}

export async function login(email: string, password: string) {
  const body = await request<{ user: unknown; tokens: Tokens }>("/v1/auth/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, device_id: getDeviceId(), device_name: "KubanFy Web", platform: "web" }),
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
