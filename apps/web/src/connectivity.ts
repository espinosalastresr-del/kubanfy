/** B3 — network connectivity helpers (no entitlement logic). */

export type ConnectivityListener = (online: boolean) => void;

const listeners = new Set<ConnectivityListener>();

function emit() {
  const online = typeof navigator !== "undefined" ? navigator.onLine : true;
  for (const fn of listeners) {
    try {
      fn(online);
    } catch {
      /* ignore */
    }
  }
}

let bound = false;

function ensureBound() {
  if (bound || typeof window === "undefined") return;
  bound = true;
  window.addEventListener("online", emit);
  window.addEventListener("offline", emit);
}

export function isOnline(): boolean {
  return typeof navigator === "undefined" ? true : navigator.onLine;
}

export function subscribeConnectivity(fn: ConnectivityListener): () => void {
  ensureBound();
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Soft probe: HEAD to same-origin (shell). Does not hit API or R2. */
export async function probeConnectivity(timeoutMs = 4000): Promise<boolean> {
  if (typeof navigator !== "undefined" && !navigator.onLine) return false;
  const ctrl = new AbortController();
  const t = window.setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch("/manifest.webmanifest", {
      method: "GET",
      cache: "no-store",
      signal: ctrl.signal,
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(t);
  }
}
