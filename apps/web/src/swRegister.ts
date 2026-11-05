/** B3 — Service Worker registration + controlled updates. */

export type SwUpdateHandlers = {
  onUpdateAvailable?: () => void;
  onControlling?: () => void;
  onRegistered?: (reg: ServiceWorkerRegistration) => void;
  onError?: (err: Error) => void;
};

let registration: ServiceWorkerRegistration | null = null;

export function getSwRegistration(): ServiceWorkerRegistration | null {
  return registration;
}

export async function registerServiceWorker(handlers: SwUpdateHandlers = {}): Promise<void> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;

  try {
    const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
    registration = reg;
    handlers.onRegistered?.(reg);

    if (reg.waiting) {
      handlers.onUpdateAvailable?.();
    }

    reg.addEventListener("updatefound", () => {
      const installing = reg.installing;
      if (!installing) return;
      installing.addEventListener("statechange", () => {
        if (installing.state === "installed" && navigator.serviceWorker.controller) {
          handlers.onUpdateAvailable?.();
        }
      });
    });

    navigator.serviceWorker.addEventListener("controllerchange", () => {
      handlers.onControlling?.();
    });

    // Check for updates periodically (every 30 min when visible).
    const check = () => {
      if (document.visibilityState === "visible") void reg.update().catch(() => {});
    };
    document.addEventListener("visibilitychange", check);
    window.setInterval(check, 30 * 60 * 1000);
  } catch (e) {
    handlers.onError?.(e instanceof Error ? e : new Error(String(e)));
  }
}

/** Activate waiting worker immediately (user accepted update). */
export function applyServiceWorkerUpdate(): void {
  const waiting = registration?.waiting;
  if (!waiting) {
    window.location.reload();
    return;
  }
  waiting.postMessage({ type: "SKIP_WAITING" });
}
