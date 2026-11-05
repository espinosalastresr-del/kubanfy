import { useEffect, useState } from "react";
import type { PlanTier } from "./cachePolicy";
import {
  isDataSaverEnabled,
  setDataSaverEnabled,
  qualityLabel,
  resolveStreamingQuality,
} from "./dataSaver";

type Props = {
  tier: PlanTier;
  setStatus: (s: string) => void;
};

export function SettingsPanel({ tier, setStatus }: Props) {
  const [dataSaver, setDataSaver] = useState(isDataSaverEnabled());

  useEffect(() => {
    const on = () => setDataSaver(isDataSaverEnabled());
    window.addEventListener("kubanfy:data-saver", on);
    return () => window.removeEventListener("kubanfy:data-saver", on);
  }, []);

  function toggle() {
    const next = !dataSaver;
    setDataSaverEnabled(next);
    setDataSaver(next);
    setStatus(
      next
        ? "Ahorro de datos activado — streaming en LOW (128 kbps)"
        : "Ahorro de datos desactivado",
    );
  }

  const effective = resolveStreamingQuality(tier, dataSaver, "medium");

  return (
    <section className="library-section">
      <h2>Ajustes</h2>
      <div className="glass" style={{ padding: 14, borderRadius: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <strong style={{ display: "block" }}>Ahorro de datos</strong>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              Fuerza LOW, reduce precarga. No otorga calidad superior al plan.
            </span>
          </div>
          <button
            className={`secondary-button${dataSaver ? " is-active" : ""}`}
            onClick={toggle}
            aria-pressed={dataSaver}
          >
            {dataSaver ? "ON" : "OFF"}
          </button>
        </div>
        <p style={{ margin: "12px 0 0", fontSize: 12, color: "var(--muted)" }}>
          Plan: <strong style={{ color: "var(--text)" }}>{tier}</strong>
          {" · "}
          Streaming efectivo: <strong style={{ color: "var(--text)" }}>{qualityLabel(effective)}</strong>
        </p>
      </div>
    </section>
  );
}
