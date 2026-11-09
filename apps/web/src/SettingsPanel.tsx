import { useEffect, useState } from "react";
import type { PlanTier } from "./cachePolicy";
import {
  isDataSaverEnabled,
  setDataSaverEnabled,
  getPreferredAudioQuality,
  setPreferredAudioQuality,
  qualityLabel,
  resolveStreamingQuality,
} from "./dataSaver";
import { getUserPreferences, updateUserPreferences, type UserPreferences } from "./api";

type Props = {
  tier: PlanTier;
  setStatus: (s: string) => void;
};

const DEFAULTS: UserPreferences = {
  audio_quality: "auto",
  data_saver: true,
  wifi_only_downloads: true,
  theme: "system",
  local_content_enabled: true,
};

function applyTheme(theme: UserPreferences["theme"]) {
  document.documentElement.dataset.theme = theme;
}

export function SettingsPanel({ tier, setStatus }: Props) {
  const [preferences, setPreferences] = useState<UserPreferences>({
    ...DEFAULTS,
    data_saver: isDataSaverEnabled(),
    audio_quality: getPreferredAudioQuality(),
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    void getUserPreferences()
      .then((remote) => {
        if (!active) return;
        setPreferences(remote);
        setDataSaverEnabled(remote.data_saver);
        setPreferredAudioQuality(remote.audio_quality);
        applyTheme(remote.theme);
      })
      .catch((error) => {
        if (active) {
          setStatus(error instanceof Error
            ? `No se pudieron sincronizar los ajustes: ${error.message}`
            : "No se pudieron sincronizar los ajustes.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [setStatus]);

  async function save(patch: Partial<UserPreferences>) {
    if (saving) return;
    const previous = preferences;
    const optimistic = { ...preferences, ...patch };
    setPreferences(optimistic);
    setSaving(true);
    try {
      const saved = await updateUserPreferences(patch);
      setPreferences(saved);
      setDataSaverEnabled(saved.data_saver);
      setPreferredAudioQuality(saved.audio_quality);
      applyTheme(saved.theme);
      setStatus("Preferencias sincronizadas.");
    } catch (error) {
      setPreferences(previous);
      setStatus(error instanceof Error
        ? `No se pudieron guardar los ajustes: ${error.message}`
        : "No se pudieron guardar los ajustes.");
    } finally {
      setSaving(false);
    }
  }

  const effective = resolveStreamingQuality(
    tier,
    preferences.data_saver,
    preferences.audio_quality === "low" ? "low" : "medium",
  );

  function toggle(
    key: "data_saver" | "wifi_only_downloads" | "local_content_enabled",
  ) {
    void save({ [key]: !preferences[key] });
  }

  return (
    <section className="library-section">
      <h2>Ajustes</h2>
      <p style={{ color: "var(--muted)", fontSize: 12, marginTop: -4 }}>
        {loading ? "Cargando preferencias…" : "Tus preferencias se sincronizan con tu cuenta."}
      </p>
      <div className="glass" style={{ padding: 14, borderRadius: 16, display: "grid", gap: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <strong style={{ display: "block" }}>Ahorro de datos</strong>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              Prioriza audio LOW y reduce precarga.
            </span>
          </div>
          <button
            className={`secondary-button${preferences.data_saver ? " is-active" : ""}`}
            onClick={() => toggle("data_saver")}
            aria-pressed={preferences.data_saver}
            disabled={loading || saving}
          >
            {preferences.data_saver ? "ON" : "OFF"}
          </button>
        </div>

        <label className="field" style={{ marginTop: 0 }}>
          <span>Calidad de audio preferida</span>
          <select
            value={preferences.audio_quality}
            disabled={loading || saving}
            onChange={(event) => void save({ audio_quality: event.target.value as UserPreferences["audio_quality"] })}
          >
            <option value="auto">Automática (recomendada)</option>
            <option value="low">Baja · 128 kbps</option>
            <option value="medium">Media · 320 kbps (según plan)</option>
            <option value="high">Máxima disponible en tu plan</option>
          </select>
        </label>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <strong style={{ display: "block" }}>Descargar solo con Wi-Fi</strong>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              Preferencia de descarga para conexiones medidas.
            </span>
          </div>
          <button
            className={`secondary-button${preferences.wifi_only_downloads ? " is-active" : ""}`}
            onClick={() => toggle("wifi_only_downloads")}
            aria-pressed={preferences.wifi_only_downloads}
            disabled={loading || saving}
          >
            {preferences.wifi_only_downloads ? "ON" : "OFF"}
          </button>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <strong style={{ display: "block" }}>Contenido local</strong>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              Mantener habilitada la biblioteca disponible sin conexión.
            </span>
          </div>
          <button
            className={`secondary-button${preferences.local_content_enabled ? " is-active" : ""}`}
            onClick={() => toggle("local_content_enabled")}
            aria-pressed={preferences.local_content_enabled}
            disabled={loading || saving}
          >
            {preferences.local_content_enabled ? "ON" : "OFF"}
          </button>
        </div>

        <label className="field" style={{ marginTop: 0 }}>
          <span>Apariencia</span>
          <select
            value={preferences.theme}
            disabled={loading || saving}
            onChange={(event) => void save({ theme: event.target.value as UserPreferences["theme"] })}
          >
            <option value="system">Según el sistema</option>
            <option value="dark">Oscuro</option>
            <option value="light">Claro</option>
          </select>
        </label>

        <p style={{ margin: 0, fontSize: 12, color: "var(--muted)" }}>
          Plan: <strong style={{ color: "var(--text)" }}>{tier}</strong>
          {" · "}
          Calidad efectiva: <strong style={{ color: "var(--text)" }}>{qualityLabel(effective)}</strong>
          {saving ? " · Guardando…" : ""}
        </p>
      </div>
    </section>
  );
}
