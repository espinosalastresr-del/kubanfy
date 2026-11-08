/**
 * B4 — Data Saver + streaming quality resolution.
 * Never grants quality above entitlement. Backend remains authority.
 */

import type { PlanTier } from "./cachePolicy";

const KEY = "kubanfy.dataSaver";
const QUALITY_KEY = "kubanfy.audioQuality";

export type StreamQuality = "low" | "medium";
export type PreferredAudioQuality = "auto" | "low" | "medium" | "high";

export function getPreferredAudioQuality(): PreferredAudioQuality {
  try {
    const value = localStorage.getItem(QUALITY_KEY);
    return value === "low" || value === "medium" || value === "high" ? value : "auto";
  } catch {
    return "auto";
  }
}

export function setPreferredAudioQuality(value: PreferredAudioQuality): void {
  try { localStorage.setItem(QUALITY_KEY, value); } catch { /* private mode */ }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("kubanfy:audio-quality", { detail: { quality: value } }));
  }
}

export function isDataSaverEnabled(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function setDataSaverEnabled(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? "1" : "0");
  } catch {
    /* private mode */
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("kubanfy:data-saver", { detail: { enabled: on } }));
  }
}

/**
 * Resolve client-requested streaming quality.
 * FREE/guest → always LOW.
 * Data Saver → always LOW (even Premium).
 * Premium family/student → MEDIUM unless Data Saver or explicit low.
 */
export function resolveStreamingQuality(
  tier: PlanTier,
  dataSaver: boolean,
  preferred: StreamQuality = "medium",
): StreamQuality {
  if (dataSaver) return "low";
  if (tier === "guest" || tier === "free") return "low";
  if (preferred === "low") return "low";
  return "medium";
}

export function qualityLabel(q: StreamQuality): string {
  return q === "medium" ? "320 kbps" : "128 kbps";
}
