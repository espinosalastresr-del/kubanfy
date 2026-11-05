import { useCallback, useEffect, useState } from "react";
import { listMyEntitlements, type EntitlementItem } from "./api";
import {
  describeEntitlement,
  featuresForTier,
  planTierFromEntitlements,
} from "./entitlements";
import type { PlanTier } from "./cachePolicy";

type Props = {
  tier: PlanTier;
  setStatus: (s: string) => void;
  onTierResolved?: (tier: PlanTier) => void;
};

export function EntitlementsPanel({ tier, setStatus, onTierResolved }: Props) {
  const [items, setItems] = useState<EntitlementItem[]>([]);
  const [busy, setBusy] = useState(false);
  const features = featuresForTier(tier);

  const refresh = useCallback(async () => {
    setBusy(true);
    try {
      const list = await listMyEntitlements();
      setItems(list);
      const resolved = planTierFromEntitlements(list);
      onTierResolved?.(resolved);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudieron cargar entitlements");
    } finally {
      setBusy(false);
    }
  }, [onTierResolved, setStatus]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section className="library-section">
      <h2>Plan y entitlements</h2>
      <div className="glass" style={{ padding: 14, borderRadius: 16, marginBottom: 12 }}>
        <p style={{ margin: "0 0 8px", fontSize: 13 }}>
          Plan efectivo: <strong>{features.label}</strong> ({tier})
        </p>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--muted)" }}>
          <li>Calidad máxima streaming: {features.qualityMax}</li>
          <li>Descargas premium: {features.downloads ? "sí" : "no"}</li>
          <li>Auto-cache (tracks): hasta {features.autoCache}</li>
        </ul>
        <p style={{ margin: "10px 0 0", fontSize: 11, color: "var(--muted)" }}>
          El cliente nunca eleva el plan por encima de lo que concede el servidor.
        </p>
        <button
          className="secondary-button"
          disabled={busy}
          onClick={() => void refresh()}
          style={{ marginTop: 12 }}
        >
          {busy ? "Cargando…" : "Actualizar entitlements"}
        </button>
      </div>

      <h3>Activos ({items.length})</h3>
      <div className="library-list">
        {items.length === 0 ? (
          <div className="empty-state">
            <span>Sin grants activos — se aplica plan Free.</span>
          </div>
        ) : (
          items.map((e) => (
            <article key={e.id} className="glass library-track">
              <div className="track-info">
                <strong>{e.scope_type}</strong>
                <span>{describeEntitlement(e)}</span>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
