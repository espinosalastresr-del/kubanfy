/** B5 — PWA install prompt (beforeinstallprompt). */

type InstallOutcome = "accepted" | "dismissed" | "unavailable";

let deferred: BeforeInstallPromptEvent | null = null;
const listeners = new Set<(available: boolean) => void>();

export type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

function emit() {
  const available = Boolean(deferred);
  for (const fn of listeners) {
    try {
      fn(available);
    } catch {
      /* ignore */
    }
  }
}

export function initInstallPromptCapture(): void {
  if (typeof window === "undefined") return;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferred = e as BeforeInstallPromptEvent;
    emit();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    emit();
  });
}

export function isInstallAvailable(): boolean {
  return Boolean(deferred);
}

export function subscribeInstallAvailable(fn: (available: boolean) => void): () => void {
  listeners.add(fn);
  fn(Boolean(deferred));
  return () => listeners.delete(fn);
}

export async function promptPwaInstall(): Promise<InstallOutcome> {
  if (!deferred) return "unavailable";
  const ev = deferred;
  deferred = null;
  emit();
  await ev.prompt();
  const { outcome } = await ev.userChoice;
  return outcome;
}

export function isStandaloneDisplay(): boolean {
  if (typeof window === "undefined") return false;
  const mq = window.matchMedia?.("(display-mode: standalone)")?.matches;
  const ios = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return Boolean(mq || ios);
}
