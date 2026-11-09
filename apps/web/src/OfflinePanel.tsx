import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  completeDownloadTicket,
  downloadTrack,
  getDeviceId,
  offlineBootstrap,
  validateOfflineLicense,
} from "./api";
import { getLicense, listTracks, putLicense, removeOfflineTrack, type OfflineTrackRecord } from "./offlineDb";
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
  const downloadController = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    const all = await listTracks();
    setTracks(all.sort((a, b) => b.updatedAt - a.updatedAt));
  }, []);

  useEffect(() => {
    void refresh().catch(() => {});
    return () => downloadController.current?.abort();
  }, [refresh]);

  function beginDownload(): AbortController {
    downloadController.current?.abort();
    const controller = new AbortController();
    downloadController.current = controller;
    return controller;
  }

  function cancelDownload() {
    downloadController.current?.abort();
    setStatus("Deteniendo descarga…");
  }

  async function runBootstrap(targetTrackId?: string) {
    const controller = beginDownload();
    setBusy(true);
    setProgress(null);
    try {
      const items = await offlineBootstrap(3, controller.signal);
      const selected = targetTrackId
        ? items.filter((item) => String(item.track_id) === targetTrackId)
        : items;
      if (!selected.length) {
        setStatus(targetTrackId
          ? "Ese track ya no pertenece al conjunto de bootstrap disponible"
          : "No hay tracks de bootstrap disponibles ahora");
        return;
      }
      const deviceId = getDeviceId();
      for (const item of selected) {
        await materializeBootstrapItem(item, deviceId, setProgress, controller.signal);
      }
      setStatus(`Bootstrap offline: ${selected.length} canción(es) listas`);
    } catch (error) {
      if (controller.signal.aborted) {
        setStatus("Descarga detenida. Puedes reanudarla sin perder los fragmentos verificados.");
      } else {
        const msg =
          error instanceof ApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : "Bootstrap offline falló";
        setStatus(msg);
      }
    } finally {
      if (downloadController.current === controller) downloadController.current = null;
      setBusy(false);
      setProgress(null);
      await refresh().catch(() => {});
    }
  }

  async function runPremiumDownload(trackIdOverride?: string) {
    const trackId = (trackIdOverride ?? premiumTrackId).trim();
    if (!trackId) {
      setStatus("Indica un track_id para descarga Premium");
      return;
    }
    const controller = beginDownload();
    setBusy(true);
    setProgress(null);
    try {
      const result = await downloadTrack(trackId, "medium", controller.signal);
      if (!result.offline_license) {
        setStatus("Sin licencia offline (¿falta X-Device-ID o entitlement?)");
        return;
      }
      const deviceId = getDeviceId();
      await materializePremiumDownload(
        trackId, trackId, result, deviceId, setProgress, controller.signal,
      );
      if (result.download_ticket) {
        try {
          await completeDownloadTicket(result.download_ticket, result.size_bytes ?? undefined);
        } catch {
          /* analytics non-fatal */
        }
      }
      setStatus("Descarga Premium almacenada offline");
      setPremiumTrackId("");
    } catch (error) {
      if (controller.signal.aborted) {
        setStatus("Descarga detenida. Puedes reanudarla sin perder los fragmentos verificados.");
      } else {
        const msg =
          error instanceof ApiError
            ? error.status === 403
              ? "Se requiere plan Premium para descargas persistentes"
              : error.message
            : error instanceof Error
              ? error.message
              : "Descarga falló";
        setStatus(msg);
      }
    } finally {
      if (downloadController.current === controller) downloadController.current = null;
      setBusy(false);
      setProgress(null);
      await refresh().catch(() => {});
    }
  }

  async function validateLicense(trackId: string) {
    try {
      const lic = await getLicense(trackId);
      if (!lic) {
        setStatus("No hay licencia local para este track");
        return;
      }
      const validated = await validateOfflineLicense(lic.token);
      if (!validated.public_key_pem) {
        throw new Error("El servidor no entregó la clave pública para validar offline.");
      }
      await putLicense({
        ...lic,
        expiresAt: validated.expires_at,
        publicKeyPem: validated.public_key_pem,
        updatedAt: Date.now(),
      });
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

      {busy && (
        <div className="offline-download-progress">
          {progress && (
            <p className="status-banner" style={{ background: "rgba(141,225,208,.12)", color: "var(--accent-2)" }}>
              {progress.trackId.slice(0, 8)}… {progress.completedChunks}/{progress.totalChunks} ({progress.status})
            </p>
          )}
          <button className="secondary-button" onClick={cancelDownload}>
            Cancelar descarga
          </button>
        </div>
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
              {t.source !== "auto" && (
                <button className="icon-button" onClick={() => void validateLicense(t.trackId)} aria-label="Validar licencia">
                  ✓
                </button>
              )}
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
                {t.source !== "auto" ? (
                  <button
                    className="secondary-button"
                    disabled={busy}
                    onClick={() => void (t.source === "bootstrap"
                      ? runBootstrap(t.trackId)
                      : runPremiumDownload(t.trackId))}
                  >
                    Reanudar
                  </button>
                ) : (
                  <span className="empty-state">Se completa al reproducir</span>
                )}
                <button className="icon-button" disabled={busy} onClick={() => void remove(t.trackId)} aria-label="Eliminar">
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
