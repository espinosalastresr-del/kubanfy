import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  clearTokens,
  getDeviceId,
  listDevices,
  listSessions,
  logoutAll,
  revokeDevice,
  revokeSession,
  updateProfile,
  type AuthDevice,
  type AuthSession,
  type UserProfile,
} from "./api";

type Props = {
  user: UserProfile | Record<string, unknown>;
  setUser: (u: any) => void;
  setStatus: (s: string) => void;
  onLoggedOut: () => void;
};

function fmt(iso?: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("es", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export function AccountPanel({ user, setUser, setStatus, onLoggedOut }: Props) {
  const u = user as UserProfile;
  const [devices, setDevices] = useState<AuthDevice[]>([]);
  const [sessions, setSessions] = useState<AuthSession[]>([]);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState(String(u.display_name || ""));
  const [country, setCountry] = useState(String(u.country || "CU"));
  const [language, setLanguage] = useState(String(u.language || "es"));
  const thisDevice = getDeviceId();
  const onLoggedOutRef = useRef(onLoggedOut);

  useEffect(() => {
    onLoggedOutRef.current = onLoggedOut;
  }, [onLoggedOut]);

  const refresh = useCallback(async () => {
    try {
      const [d, s] = await Promise.all([listDevices(), listSessions()]);
      setDevices(d);
      setSessions(s);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        clearTokens();
        onLoggedOutRef.current();
        return;
      }
      setStatus(e instanceof Error ? e.message : "No se pudo cargar cuenta");
    }
  }, [setStatus]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const updated = await updateProfile({
        display_name: name.trim(),
        country: country.trim().toUpperCase(),
        language: language.trim().toLowerCase(),
      });
      setUser(updated);
      setStatus("Perfil actualizado");
    } catch (err) {
      setStatus(err instanceof ApiError ? err.message : "No se pudo guardar el perfil");
    } finally {
      setBusy(false);
    }
  }

  async function removeDevice(id: string) {
    setBusy(true);
    try {
      await revokeDevice(id);
      setStatus("Dispositivo revocado");
      await refresh();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "No se pudo revocar");
    } finally {
      setBusy(false);
    }
  }

  async function removeSession(id: string) {
    setBusy(true);
    try {
      await revokeSession(id);
      setStatus("Sesión cerrada");
      await refresh();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "No se pudo cerrar la sesión");
    } finally {
      setBusy(false);
    }
  }

  async function doLogoutAll() {
    if (!confirm("¿Cerrar sesión en todos los dispositivos?")) return;
    setBusy(true);
    try {
      await logoutAll();
    } catch {
      /* still clear local */
    }
    onLoggedOut();
    setStatus("Sesiones cerradas");
    setBusy(false);
  }

  return (
    <section className="library-section">
      <h2>Cuenta</h2>
      <div className="glass" style={{ padding: 14, borderRadius: 16, marginBottom: 12 }}>
        <p style={{ margin: "0 0 8px", fontSize: 13, color: "var(--muted)" }}>
          {String(u.email || "")}
          {u.email_verified ? " · verificado" : " · sin verificar"}
        </p>
        <form onSubmit={saveProfile}>
          <label className="field">
            <span>Nombre</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
          </label>
          <label className="field">
            <span>País (ISO)</span>
            <input value={country} onChange={(e) => setCountry(e.target.value)} required maxLength={2} />
          </label>
          <label className="field">
            <span>Idioma</span>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              style={{
                width: "100%",
                border: "1px solid var(--border)",
                background: "rgba(7,9,13,.34)",
                color: "var(--text)",
                borderRadius: 16,
                padding: "14px 15px",
              }}
            >
              <option value="es">Español</option>
              <option value="en">English</option>
            </select>
          </label>
          <button className="secondary-button" type="submit" disabled={busy} style={{ marginTop: 12 }}>
            Guardar perfil
          </button>
        </form>
      </div>

      <h3>Dispositivos ({devices.length})</h3>
      <div className="library-list" style={{ marginBottom: 16 }}>
        {devices.length === 0 ? (
          <div className="empty-state">
            <span>No hay dispositivos registrados.</span>
          </div>
        ) : (
          devices.map((d) => {
            const isThis = d.device_id === thisDevice;
            return (
              <article key={d.id} className="glass library-track">
                <div className="track-info">
                  <strong>
                    {d.name || d.platform || "Dispositivo"}
                    {isThis ? " (este)" : ""}
                  </strong>
                  <span>
                    {d.status} · visto {fmt(d.last_seen_at)}
                  </span>
                </div>
                {!isThis && (
                  <button
                    className="icon-button"
                    disabled={busy}
                    onClick={() => void removeDevice(d.id)}
                    aria-label="Revocar dispositivo"
                  >
                    ×
                  </button>
                )}
              </article>
            );
          })
        )}
      </div>

      <h3>Sesiones ({sessions.length})</h3>
      <div className="library-list" style={{ marginBottom: 16 }}>
        {sessions.length === 0 ? (
          <div className="empty-state">
            <span>No hay sesiones activas listadas.</span>
          </div>
        ) : (
          sessions.map((s) => (
            <article key={s.id} className="glass library-track">
              <div className="track-info">
                <strong>
                  {s.ip_country || "—"} · {s.status}
                </strong>
                <span>
                  actividad {fmt(s.last_activity_at)} · expira {fmt(s.expires_at)}
                </span>
              </div>
              <button
                className="icon-button"
                disabled={busy}
                onClick={() => void removeSession(s.id)}
                aria-label="Cerrar sesión"
              >
                ×
              </button>
            </article>
          ))
        )}
      </div>

      <button className="secondary-button" disabled={busy} onClick={() => void doLogoutAll()}>
        Cerrar sesión en todos los dispositivos
      </button>
    </section>
  );
}
