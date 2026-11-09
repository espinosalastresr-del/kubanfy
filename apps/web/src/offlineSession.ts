import type { PlanTier } from "./cachePolicy";

const STORAGE_KEY = "kubanfy.offline-session.v1";
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

export type OfflineSessionSnapshot = {
  user: {
    id: string;
    email?: string;
    display_name: string;
    avatar: string | null;
    country: string;
    language: string;
    status: string;
    email_verified: boolean;
  };
  planTier: PlanTier;
  savedAt: number;
};

export function saveOfflineSessionSnapshot(user: any, planTier: PlanTier): void {
  if (!user || typeof user.id !== "string" || !user.id) return;
  const snapshot: OfflineSessionSnapshot = {
    user: {
      id: user.id,
      ...(typeof user.email === "string" ? { email: user.email } : {}),
      display_name: typeof user.display_name === "string" ? user.display_name : "Usuario",
      avatar: typeof user.avatar === "string" ? user.avatar : null,
      country: typeof user.country === "string" ? user.country : "",
      language: typeof user.language === "string" ? user.language : "es",
      status: typeof user.status === "string" ? user.status : "active",
      email_verified: Boolean(user.email_verified),
    },
    planTier,
    savedAt: Date.now(),
  };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // Restricted storage means offline account restoration is unavailable.
  }
}

export function readOfflineSessionSnapshot(): OfflineSessionSnapshot | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const snapshot = JSON.parse(raw) as OfflineSessionSnapshot;
    const age = Date.now() - Number(snapshot.savedAt);
    const allowedTiers: PlanTier[] = ["guest", "free", "premium", "family", "student"];
    if (
      !snapshot.user?.id ||
      !snapshot.user?.display_name ||
      snapshot.user.status !== "active" ||
      !allowedTiers.includes(snapshot.planTier) ||
      !Number.isFinite(age) ||
      age < 0 ||
      age > MAX_AGE_MS
    ) return null;
    return snapshot;
  } catch {
    return null;
  }
}

export function clearOfflineSessionSnapshot(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Best effort.
  }
}
