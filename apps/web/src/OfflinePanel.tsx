import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  completeDownloadTicket,
  downloadTrack,
  getDeviceId,
  offlineBootstrap,
  validateOfflineLicense,
} from "./api";
import { listTracks, removeOfflineTrack, type OfflineTrackRecord } from "./offlineDb";
import {
  materializeBootstrapItem,
  materializePremiumDownload,
  type DownloadProgress,
} from "./offlineDownload";

type Props = {
  setStatus: (s: string) => void;
  onPlayOnline?: (trackId: string) => void;
};

export function OfflinePanel({ setStatus, onPlayOnline }: Props) {
  const [tracks, setTracks] = useState<OfflineTrackRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<DownloadProgress | null>(null);
  const [premiumTrackId, setPremiumTrackId] = useState("");

  const refresh = useCallback(async () => {
    const all = await listTracks();
    setTracks(all.sort((a, b) => b.updatedAt - a.updatedAt));
  }, []);

  useEffect(() => {
    void refresh().catch(() => {});
  }, [refresh]);

  async function runBootstrap() {
    setBusy(true);
    setProgress(null);
    try {
      const items = await offlineBootstrap(3);
      if (!items.length) {
        setStatus("No hay tracks de bootstrap disponibles ahora");
        return;
      }
      const deviceId = getDeviceId();
      for (const item of items) {
        await materializeBootstrapItem(item, deviceId, setProgress);
      }
      setStatus(`Bootstrap offline: ${items.length} canción(es) listas`);
      await refresh();
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Bootstrap offline falló";
      setStatus(msg);
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  async function runPremiumDownload() {
    const trackId = premiumTrackId.trim();
    if (!trackId) {
      setStatus("Indica un track_id para descarga Premium");
      return;
    }
    setBusy(true);
    setProgress(null);
    try {
      const result = await downloadTrack(trackId, "medium");
      if (!result.offline_license) {
        setStatus("Sin licencia offline (¿falta X-Device-ID o entitlement?)");
        return;
      }
      const deviceId = getDeviceId();
      await materializePremiumDownload(trackId, trackId, result, deviceId, setProgress);
      if (result.download_ticket) {
        try {
          await completeDownloadTicket(result.download_ticket, result.size_bytes ?? undefined);
        } catch {
          /* analytics non-fatal */
        }
      }
      setStatus("Descarga Premium almacenada offline");
      setPremiumTrackId("");
      await refresh();
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.status === 403
            ? "Se requiere plan Premium para descargas persistentes"
            : e.message
          : e instanceof Error
            ? e.message
            : "Descarga falló";
      setStatus(msg);
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  async function validateLicense(trackId: string) {
    try {
      const { getLicense } = await import("./offlineDb");
      const lic = await getLicense(trackId);
      if (!lic) {
        setStatus("No hay licencia local para este track");
        return;
      }
      const validated = await validateOfflineLicense(lic.token);
      setStatus(`Licencia OK · expira ${validated.expires_at}`);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Validación de licencia falló");
    }
  }

  async function remove(trackId: string) {
    await removeOfflineTrack(trackId);
    await refresh();
    setStatus("Eliminado del almacén offline");
  }

  const ready = tracks.filter(
    (t) =>
      t.status === "ready" &&
      t.totalChunks > 0 &&
      t.completedChunks === t.totalChunks &&
      Boolean(t.headerBytesB64),
  );
  const partial = tracks.filter((t) => !ready.some((r) => r.trackId === t.trackId));

  return (
    <section className="library-section">
      <h2>Offline</h2>
      <p className="empty-state" style={{ padding: "8px 0", textAlign: "left" }}>
        Bootstrap gratuito (hasta 3) o descarga Premium con licencia RS256. Una descarga incompleta no se
        muestra como disponible.
      </p>

      <div className="playlist-create glass">
        <button className="primary-button" disabled={busy} onClick={() => void runBootstrap()}>
          {busy && progress ? `Descargando ${progress.completedChunks}/${progress.totalChunks}` : "Bootstrap offline"}
        </button>
      </div>

      <div className="playlist-create glass">
        <input
          value={premiumTrackId}
          onChange={(e) => setPremiumTrackId(e.target.value)}
          placeholder="track_id Premium"
          disabled={busy}
        />
        <button className="secondary-button" disabled={busy || !premiumTrackId.trim()} onClick={() => void runPremiumDownload()}>
          Descargar
        </button>
      </div>

      {progress && (
        <p className="status-banner" style={{ background: "rgba(141,225,208,.12)", color: "var(--accent-2)" }}>
          {progress.trackId.slice(0, 8)}… {progress.completedChunks}/{progress.totalChunks} ({progress.status})
        </p>
      )}

      <h3>Listas ({ready.length})</h3>
      {ready.length === 0 ? (
        <div className="empty-state">
          <strong>Nada listo offline</strong>
          <span>Ejecuta bootstrap o una descarga Premium completa.</span>
        </div>
      ) : (
        <div className="library-list">
          {ready.map((t) => (
            <article key={t.trackId} className="glass library-track">
              <button className="track-info" onClick={() => onPlayOnline?.(t.trackId)}>
                <strong>{t.title}</strong>
                <span>
                  ▶ offline · {t.source} · {t.quality} · v{t.assetVersion} · {t.completedChunks}/{t.totalChunks} chunks
                </span>
              </button>
              <button className="icon-button" onClick={() => void validateLicense(t.trackId)} aria-label="Validar licencia">
                ✓
              </button>
              <button className="icon-button" onClick={() => void remove(t.trackId)} aria-label="Eliminar offline">
                ×
              </button>
            </article>
          ))}
        </div>
      )}

      {partial.length > 0 && (
        <>
          <h3>Incompletas (no reproducibles)</h3>
          <div className="library-list">
            {partial.map((t) => (
              <article key={t.trackId} className="glass library-track">
                <div className="track-info">
                  <strong>{t.title}</strong>
                  <span>
                    {t.status} · {t.completedChunks}/{t.totalChunks}
                  </span>
                </div>
                <button className="icon-button" onClick={() => void remove(t.trackId)} aria-label="Eliminar">
                  ×
                </button>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
