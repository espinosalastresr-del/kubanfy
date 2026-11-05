import { useCallback, useEffect, useState } from "react";
import { getDeviceId } from "./api";
import { isOnline, probeConnectivity } from "./connectivity";
import { getSwRegistration } from "./swRegister";
import { isDataSaverEnabled } from "./dataSaver";
import type { PlanTier } from "./cachePolicy";
import { isInstallAvailable, isStandaloneDisplay, promptPwaInstall } from "./installPrompt";
import { listReadyTracks } from "./offlineDb";

type Props = {
  tier: PlanTier;
  setStatus: (s: string) => void;
};

export function DiagnosticsPanel({ tier, setStatus }: Props) {
  const [online, setOnlineState] = useState(isOnline());
  const [probe, setProbe] = useState<boolean | null>(null);
  const [swState, setSwState] = useState("—");
  const [offlineCount, setOfflineCount] = useState(0);
  const [installOk, setInstallOk] = useState(isInstallAvailable());
  const [standalone] = useState(isStandaloneDisplay());
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setOnlineState(isOnline());
    setInstallOk(isInstallAvailable());
    const reg = getSwRegistration();
    if (!reg) setSwState("no registrado");
    else if (reg.waiting) setSwState("update pending");
    else if (reg.active) setSwState(reg.active.state);
    else setSwState("registrado");
    try {
      const ready = await listReadyTracks();
      setOfflineCount(ready.length);
    } catch {
      setOfflineCount(0);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function runProbe() {
    setBusy(true);
    try {
      const ok = await probeConnectivity(4000);
      setProbe(ok);
      setStatus(ok ? "Probe shell OK" : "Probe shell falló (offline o SW)");
    } finally {
      setBusy(false);
      void refresh();
    }
  }

  async function install() {
    const outcome = await promptPwaInstall();
    if (outcome === "accepted") setStatus("App instalada");
    else if (outcome === "dismissed") setStatus("Instalación cancelada");
    else setStatus("Instalación no disponible en este navegador");
    void refresh();
  }

  const row = (k: string, v: string) => (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: 13, padding: "6px 0" }}>
      <span style={{ color: "var(--muted)" }}>{k}</span>
      <strong style={{ textAlign: "right" }}>{v}</strong>
    </div>
  );

  return (
    <section className="library-section">
      <h2>Diagnóstico</h2>
      <div className="glass" style={{ padding: 14, borderRadius: 16 }}>
        {row("Red (navigator)", online ? "online" : "offline")}
        {row("Probe shell", probe === null ? "—" : probe ? "OK" : "fallo")}
        {row("Service Worker", swState)}
        {row("PWA standalone", standalone ? "sí" : "no")}
        {row("Install disponible", installOk ? "sí" : "no")}
        {row("Plan", tier)}
        {row("Data Saver", isDataSaverEnabled() ? "ON" : "OFF")}
        {row("Tracks offline ready", String(offlineCount))}
        {row("Device ID", getDeviceId().slice(0, 8) + "…")}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          <button className="secondary-button" disabled={busy} onClick={() => void runProbe()}>
            Probar shell
          </button>
          <button className="secondary-button" disabled={!installOk || standalone} onClick={() => void install()}>
            Instalar app
          </button>
          <button className="secondary-button" onClick={() => void refresh()}>
            Refrescar
          </button>
        </div>
      </div>
    </section>
  );
}
