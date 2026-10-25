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

// Keep local/staging builds aligned with the Cloudflare staging deployment.
// CI can override this at build time for other environments.
const API = (import.meta.env.VITE_API_BASE_URL || "https://kubanfy-api-staging.globumlatinmusic.workers.dev").replace(/\/+$/, "");
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
  const body = await request<{ user: CurrentUser; tokens: Tokens }>("/v1/auth/login", {
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

const DISCOVERY_CACHE_KEY = "kubanfy:discovery-home:v1";
const OFFLINE_CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000;

function readOfflineCache<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const cached = JSON.parse(raw) as { saved_at: number; data: T };
    if (!cached || typeof cached.saved_at !== "number" || Date.now() - cached.saved_at > OFFLINE_CACHE_TTL_MS) {
      localStorage.removeItem(key);
      return null;
    }
    return cached.data;
  } catch {
    return null;
  }
}

function writeOfflineCache<T>(key: string, data: T) {
  try {
    localStorage.setItem(key, JSON.stringify({ saved_at: Date.now(), data }));
  } catch {
    // Storage can be disabled or full; the online feature must still work.
  }
}

export async function discoveryHome() {
  try {
    const data = await request<DiscoveryHome>("/v1/discovery/home");
    writeOfflineCache(DISCOVERY_CACHE_KEY, data);
    return data;
  } catch (error) {
    const cached = readOfflineCache<DiscoveryHome>(DISCOVERY_CACHE_KEY);
    if (cached) return cached;
    throw error;
  }
}

export async function requestPasswordReset(email: string) {
  return request<{ message: string }>("/v1/auth/password-reset/request", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  }, false);
}

export async function confirmPasswordReset(token: string, newPassword: string) {
  return request<{ message: string }>("/v1/auth/password-reset/confirm", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  }, false);
}

export type CurrentUser = {
  id: string; email: string; display_name: string; avatar: string | null;
  country: string; language: string; status: string; email_verified: boolean;
  created_at: string; last_login_at: string | null;
};
export type UserEntitlement = {
  id: string; scope_type: string; scope_id: string | null; source: string;
  status: string; starts_at: string; expires_at: string | null; created_at: string;
  plan_code: "free" | "premium" | "family" | "student" | null;
  features: { downloads?: boolean; quality_max?: string; seats?: number };
};
export async function me() { return request<CurrentUser>("/v1/auth/me"); }
export async function updateMyProfile(profile: Pick<CurrentUser, "display_name" | "country" | "language">) {
  return request<CurrentUser>("/v1/auth/me", {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profile),
  });
}
export async function listMyEntitlements() {
  return request<UserEntitlement[]>("/v1/entitlements/me");
}
export async function searchTracks(q: string) {
  const normalized = q.trim();
  const cacheKey = `kubanfy:search:v1:${normalized.toLocaleLowerCase().slice(0, 120)}`;
  try {
    const data = await request<SearchResult[]>(`/v1/music/search?q=${encodeURIComponent(normalized)}&limit=20`);
    writeOfflineCache(cacheKey, data);
    return data;
  } catch (error) {
    const cached = readOfflineCache<SearchResult[]>(cacheKey);
    if (cached) return cached;
    throw error;
  }
}

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
export async function deletePlaylist(id: string) {
  return request<void>(`/v1/playlists/${id}`, { method: "DELETE" });
}
export async function addTrackToPlaylist(playlistId: string, trackId: string) {
  return request<void>(`/v1/playlists/${playlistId}/tracks/${trackId}`, { method: "POST" });
}


export type AdminUser = {
  id: string;
  email: string;
  display_name: string;
  status: string;
  email_verified: boolean;
  created_at: string;
  plan_code: "free" | "premium" | "family" | "student";
};

export async function listAdminUsers(search = "", limit = 50, offset = 0) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (search.trim()) params.set("q", search.trim());
  return request<AdminUser[]>(`/v1/admin/users?${params.toString()}`);
}

export async function updateAdminUserPlan(
  userId: string,
  planCode: AdminUser["plan_code"],
  reason: string,
  expiresAt?: string,
) {
  return request<{ id: string; email: string; plan_code: AdminUser["plan_code"]; expires_at: string | null }>(
    `/v1/admin/users/${encodeURIComponent(userId)}/plan`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan_code: planCode,
        reason,
        ...(expiresAt ? { expires_at: expiresAt } : {}),
      }),
    },
  );
}

export async function canManageUserPlans() {
  try {
    await request<{ allowed: boolean }>("/v1/admin/plan-access");
    return true;
  } catch {
    return false;
  }
}


export type ArtistProfile = {
  id: string;
  name: string;
  slug: string;
  bio: string | null;
  country: string;
  status: string;
  verified: boolean;
  created_at: string;
};
export type ArtistManagedTrack = {
  id: string;
  title: string;
  status: string;
  duration: number | null;
  release_id: string;
  release_title: string;
};
export async function listMyArtists() {
  return request<ArtistProfile[]>("/v1/artist/mine");
}
export async function createArtist(name: string, bio: string, country: string) {
  return request<ArtistProfile>("/v1/artist", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, bio: bio || null, country }),
  });
}
export async function updateArtist(artistId: string, name: string, bio: string, country: string) {
  return request<ArtistProfile>(`/v1/artist/${encodeURIComponent(artistId)}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, bio: bio || null, country }),
  });
}
export async function listArtistTracks(artistId: string) {
  return request<ArtistManagedTrack[]>(`/v1/artist/${encodeURIComponent(artistId)}/manage/tracks`);
}
export async function uploadArtistTrack(artistId: string, title: string, file: File, acceptLicense: boolean, explicit: boolean, language: string) {
  const body = new FormData();
  body.set("title", title);
  body.set("file", file);
  body.set("accept_license", String(acceptLicense));
  body.set("explicit", String(explicit));
  body.set("language", language);
  return request<{ track_id: string; status: string; duration: number | null; job_id: string | null }>(
    `/v1/artist/${encodeURIComponent(artistId)}/tracks/upload`, { method: "POST", body },
  );
}
export async function publishArtistTrack(artistId: string, trackId: string) {
  return request<{ track_id: string; status: string }>(
    `/v1/artist/${encodeURIComponent(artistId)}/tracks/${encodeURIComponent(trackId)}/publish`, { method: "POST" },
  );
}


export type ModerationReport = {
  id: string; target_type: "track" | "artist" | "user" | "release"; target_id: string;
  report_type: string; status: "open" | "reviewing" | "resolved" | "rejected";
  description: string | null; created_at: string;
};
export type AdminFeatureFlag = { key: string; enabled: boolean; description: string | null };
export type AdminAuditLog = {
  id: string; actor_id: string | null; action: string; target_type: string | null;
  target_id: string | null; result: string; reason: string | null; created_at: string;
  before?: Record<string, unknown> | null; after?: Record<string, unknown> | null;
};
export async function suspendAdminUser(userId: string, reason: string) {
  return request<{ id: string; status: string }>(`/v1/admin/users/${encodeURIComponent(userId)}/suspend`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reason }),
  });
}
export async function unsuspendAdminUser(userId: string) {
  return request<{ id: string; status: string }>(`/v1/admin/users/${encodeURIComponent(userId)}/unsuspend`, { method: "POST" });
}
export async function listModerationReports(status = "") {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  return request<ModerationReport[]>(`/v1/admin/moderation/reports${params.size ? `?${params}` : ""}`);
}
export async function resolveModerationReport(id: string, status: ModerationReport["status"], notes: string, takedownTrack: boolean) {
  return request<{ id: string; status: string }>(`/v1/admin/moderation/reports/${encodeURIComponent(id)}/resolve`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes: notes || null, takedown_track: takedownTrack }),
  });
}
export async function listAdminFeatureFlags() {
  return request<AdminFeatureFlag[]>("/v1/admin/feature-flags");
}
export async function updateAdminFeatureFlag(key: string, enabled: boolean) {
  return request<{ key: string; enabled: boolean }>(`/v1/admin/feature-flags/${encodeURIComponent(key)}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled }),
  });
}
export async function listAdminAuditLogs(limit = 100) {
  return request<AdminAuditLog[]>(`/v1/admin/audit-logs?limit=${Math.min(200, Math.max(1, limit))}`);
}
