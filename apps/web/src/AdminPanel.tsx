import { useEffect, useState, type FormEvent } from "react";
import {
  createAdminArtist,
  getAdminCatalog,
  publishAdminTrack,
  setAdminTrackStatus,
  updateAdminTrack,
  uploadAdminTrack,
  type AdminCatalog,
  type AdminCatalogTrack,
} from "./api";

type Props = { setStatus: (message: string) => void };

function durationLabel(value: number | null): string {
  if (!value || !Number.isFinite(value)) return "—";
  const seconds = Math.floor(value);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function AdminPanel({ setStatus }: Props) {
  const [catalog, setCatalog] = useState<AdminCatalog>({ artists: [], tracks: [] });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [selectedArtist, setSelectedArtist] = useState("");
  const [artistName, setArtistName] = useState("");
  const [artistCountry, setArtistCountry] = useState("CU");
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("es");
  const [explicit, setExplicit] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [editingTitles, setEditingTitles] = useState<Record<string, string>>({});

  async function refresh() {
    const data = await getAdminCatalog();
    setCatalog(data);
    setSelectedArtist((current) =>
      current && data.artists.some((artist) => artist.id === current)
        ? current
        : data.artists[0]?.id || "",
    );
  }

  useEffect(() => {
    void refresh()
      .catch((error) => setStatus(error instanceof Error ? error.message : "No se pudo cargar el catálogo"))
      .finally(() => setLoading(false));
  }, []);

  async function addArtist(event: FormEvent) {
    event.preventDefault();
    if (!artistName.trim()) return;
    setBusy(true);
    try {
      const artist = await createAdminArtist({ name: artistName.trim(), country: artistCountry.toUpperCase() });
      await refresh();
      setSelectedArtist(artist.id);
      setArtistName("");
      setStatus("Artista añadido al catálogo");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudo crear el artista");
    } finally {
      setBusy(false);
    }
  }

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!selectedArtist || !title.trim() || !audioFile || !accepted) return;
    if (audioFile.size > 100 * 1024 * 1024) {
      setStatus("El archivo supera el límite de 100 MB");
      return;
    }
    setBusy(true);
    try {
      const result = await uploadAdminTrack(selectedArtist, {
        title: title.trim(),
        file: audioFile,
        explicit,
        language,
      });
      setTitle("");
      setAudioFile(null);
      setAccepted(false);
      const picker = document.getElementById("admin-audio-file") as HTMLInputElement | null;
      if (picker) picker.value = "";
      await refresh();
      setStatus(result.status === "processing"
        ? "Canción recibida. Se está procesando el audio."
        : "Canción subida");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudo subir la canción");
    } finally {
      setBusy(false);
    }
  }

  async function publish(track: AdminCatalogTrack) {
    const artistId = track.artist_ids[0];
    if (!artistId) return;
    setBusy(true);
    try {
      await publishAdminTrack(artistId, track.id);
      await refresh();
      setStatus("Canción publicada");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudo publicar");
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(track: AdminCatalogTrack, status: "hidden" | "takedown" | "deleted") {
    const artistId = track.artist_ids[0];
    if (!artistId) return;
    const action = status === "deleted" ? "eliminar" : status === "hidden" ? "ocultar" : "retirar";
    if (!window.confirm(`¿Confirmas ${action} «${track.title}»?`)) return;
    setBusy(true);
    try {
      await setAdminTrackStatus(artistId, track.id, status);
      await refresh();
      setStatus(status === "hidden" ? "Canción ocultada" : status === "deleted" ? "Canción eliminada" : "Canción retirada");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudo cambiar el estado");
    } finally {
      setBusy(false);
    }
  }

  async function saveTitle(track: AdminCatalogTrack) {
    const nextTitle = (editingTitles[track.id] ?? track.title).trim();
    if (!nextTitle || nextTitle === track.title) return;
    setBusy(true);
    try {
      await updateAdminTrack(track.id, {
        title: nextTitle,
        isrc: track.isrc,
        explicit: track.explicit,
        language: track.language,
        release_date: track.release_date,
        artwork_url: track.artwork_url,
        release_id: track.release_id,
      });
      setEditingTitles((current) => {
        const next = { ...current };
        delete next[track.id];
        return next;
      });
      await refresh();
      setStatus("Metadatos actualizados");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudieron guardar los metadatos");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="admin-catalog">
      <div className="admin-heading">
        <div>
          <span className="eyebrow">CONTROL DE CONTENIDO</span>
          <h2>Catálogo musical</h2>
          <p>Sube, procesa, publica y administra las canciones de KubanFy.</p>
        </div>
        <button className="secondary-button" onClick={() => void refresh()} disabled={busy || loading}>
          Actualizar
        </button>
      </div>

      <form className="glass admin-card" onSubmit={addArtist}>
        <h3>Artistas</h3>
        <div className="admin-form-grid">
          <label className="field">
            <span>Nombre del artista</span>
            <input value={artistName} onChange={(event) => setArtistName(event.target.value)} maxLength={255} required />
          </label>
          <label className="field">
            <span>País (ISO)</span>
            <input value={artistCountry} onChange={(event) => setArtistCountry(event.target.value.toUpperCase())} maxLength={2} minLength={2} required />
          </label>
        </div>
        <button className="secondary-button" type="submit" disabled={busy || !artistName.trim()}>
          Añadir artista
        </button>
        <label className="field">
          <span>Artista para la subida</span>
          <select value={selectedArtist} onChange={(event) => setSelectedArtist(event.target.value)} required>
            <option value="">Seleccionar artista</option>
            {catalog.artists.map((artist) => (
              <option key={artist.id} value={artist.id}>{artist.name} · {artist.country}</option>
            ))}
          </select>
        </label>
        <p className="admin-muted">{catalog.artists.length} artistas registrados</p>
      </form>

      <form className="glass admin-card" onSubmit={upload}>
        <h3>Subir canción</h3>
        <label className="field">
          <span>Título</span>
          <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={255} required />
        </label>
        <div className="admin-form-grid">
          <label className="field">
            <span>Idioma</span>
            <select value={language} onChange={(event) => setLanguage(event.target.value)}>
              <option value="es">Español</option>
              <option value="en">English</option>
              <option value="pt">Português</option>
              <option value="fr">Français</option>
              <option value="other">Otro</option>
            </select>
          </label>
          <label className="field">
            <span>Archivo de audio (máx. 100 MB)</span>
            <input
              id="admin-audio-file"
              type="file"
              accept=".mp3,.flac,.wav,.m4a,.aac,.ogg,audio/*"
              onChange={(event) => setAudioFile(event.target.files?.[0] || null)}
              required
            />
          </label>
        </div>
        <label className="admin-check">
          <input type="checkbox" checked={explicit} onChange={(event) => setExplicit(event.target.checked)} />
          Contenido explícito
        </label>
        <label className="admin-check">
          <input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} required />
          Confirmo que KubanFy tiene autorización para almacenar, procesar y distribuir este audio.
        </label>
        <button className="primary-button" type="submit" disabled={busy || loading || !selectedArtist || !title.trim() || !audioFile || !accepted}>
          {busy ? "Procesando…" : "Subir y procesar"}
        </button>
        <p className="admin-muted">El audio se almacena cifrado. La publicación se habilita después de generar las calidades LOW y MEDIUM.</p>
      </form>

      <div className="admin-catalog-list">
        <div className="admin-list-heading">
          <h3>Canciones ({catalog.tracks.length})</h3>
          <span className="admin-muted">Estado y derivados de audio</span>
        </div>
        {loading ? <div className="empty-state">Cargando catálogo…</div> : catalog.tracks.length === 0 ? (
          <div className="empty-state">Todavía no hay canciones registradas.</div>
        ) : catalog.tracks.map((track) => {
          const qualities = new Set(track.assets.map((asset) => asset.quality));
          const ready = qualities.has("low") && qualities.has("medium");
          return (
            <article className="glass admin-track" key={track.id}>
              <div className="admin-track-main">
                <div className="admin-track-title">
                  <input
                    aria-label={`Título de ${track.title}`}
                    value={editingTitles[track.id] ?? track.title}
                    onChange={(event) => setEditingTitles((current) => ({ ...current, [track.id]: event.target.value }))}
                    disabled={busy}
                  />
                  {editingTitles[track.id] !== undefined && editingTitles[track.id] !== track.title && (
                    <button className="secondary-button" onClick={() => void saveTitle(track)} disabled={busy}>Guardar</button>
                  )}
                </div>
                <span>{track.artists.join(", ") || "Artista desconocido"} · {durationLabel(track.duration)}</span>
                <span className="admin-track-meta">
                  <b className={`admin-status status-${track.status}`}>{track.status}</b>
                  <span>LOW {qualities.has("low") ? "✓" : "—"}</span>
                  <span>MEDIUM {qualities.has("medium") ? "✓" : "—"}</span>
                </span>
              </div>
              <div className="admin-track-actions">
                {track.status !== "published" && track.status !== "takedown" && track.status !== "deleted" && ready && (
                  <button className="secondary-button" onClick={() => void publish(track)} disabled={busy}>Publicar</button>
                )}
                {track.status === "published" && (
                  <button className="secondary-button" onClick={() => void changeStatus(track, "hidden")} disabled={busy}>Ocultar</button>
                )}
                {track.status !== "takedown" && track.status !== "deleted" && (
                  <button className="secondary-button" onClick={() => void changeStatus(track, "takedown")} disabled={busy}>Retirar</button>
                )}
                {track.status !== "deleted" && (
                  <button className="icon-button" onClick={() => void changeStatus(track, "deleted")} disabled={busy} aria-label="Eliminar canción">×</button>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
