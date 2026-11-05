/**
 * B7 — Entitlements client. Never elevates plan beyond server grants.
 * Maps /v1/entitlements/me → PlanTier for streaming/cache policy.
 */

import type { PlanTier } from "./cachePolicy";

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

/** Resolve tier strictly from active entitlements (and optional user fields as weak hint only for display). */
export function planTierFromEntitlements(items: EntitlementItem[]): PlanTier {
  const scopes = items
    .filter((e) => String(e.status).toLowerCase() === "active")
    .map((e) => String(e.scope_type).toLowerCase());

  if (scopes.some((s) => s.includes("family"))) return "family";
  if (scopes.some((s) => s.includes("student"))) return "student";
  if (scopes.some((s) => s.includes("premium") || s === "user_premium")) return "premium";
  return "free";
}

export function describeEntitlement(e: EntitlementItem): string {
  const scope = e.scope_type.replace(/_/g, " ");
  const exp = e.expires_at
    ? ` · expira ${new Date(e.expires_at).toLocaleDateString("es")}`
    : " · sin caducidad";
  return `${scope} (${e.source})${exp}`;
}

export function featuresForTier(tier: PlanTier): {
  qualityMax: "low" | "medium";
  downloads: boolean;
  autoCache: number;
  label: string;
} {
  if (tier === "premium" || tier === "family" || tier === "student") {
    return {
      qualityMax: "medium",
      downloads: true,
      autoCache: 50,
      label: tier === "family" ? "Family" : tier === "student" ? "Student" : "Premium",
    };
  }
  if (tier === "guest") {
    return { qualityMax: "low", downloads: false, autoCache: 0, label: "Invitado" };
  }
  return { qualityMax: "low", downloads: false, autoCache: 3, label: "Free" };
}
