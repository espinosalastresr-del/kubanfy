import { useState } from "react";
import {
  createPlaylist,
  deletePlaylist,
  getPlaylist,
  listPlaylistTracks,
  removeTrackFromPlaylist,
  renamePlaylist,
  reorderPlaylistTracks,
} from "./api";
import { trackArtistsLabel } from "./queue";
import { enrichTrackIds, resolveTrackId } from "./trackMeta";

type Props = {
  playlists: any[];
  setPlaylists: (updater: any[] | ((prev: any[]) => any[])) => void;
  favorites: any[];
  favoriteIds: Set<string>;
  onToggleFavorite: (id: string) => void;
  onPlay: (id: string, queue?: string[]) => void;
  setStatus: (s: string) => void;
};

export function LibraryPanel({
  playlists,
  setPlaylists,
  favorites,
  favoriteIds,
  onToggleFavorite,
  onPlay,
  setStatus,
}: Props) {
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<string | null>(null);
  const [selectedPlaylistName, setSelectedPlaylistName] = useState("");
  const [selectedPlaylistVisibility, setSelectedPlaylistVisibility] = useState<"private" | "public">("private");
  const [selectedPlaylistTracks, setSelectedPlaylistTracks] = useState<any[]>([]);
  const [playlistDetailBusy, setPlaylistDetailBusy] = useState(false);
  const [editingPlaylistId, setEditingPlaylistId] = useState<string | null>(null);
  const [playlistNameDraft, setPlaylistNameDraft] = useState("");
  const [newPlaylistName, setNewPlaylistName] = useState("");
  const [libraryBusy, setLibraryBusy] = useState(false);

  async function makePlaylist() {
    const name = newPlaylistName.trim();
    if (!name) return;
    setLibraryBusy(true);
    try {
      const created = await createPlaylist(name);
      setPlaylists((prev) => [created, ...prev]);
      setNewPlaylistName("");
      setStatus(`Playlist «${created.name || name}» creada`);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No pudimos crear la playlist");
    } finally {
      setLibraryBusy(false);
    }
  }

  async function removePlaylist(id: string) {
    setLibraryBusy(true);
    try {
      await deletePlaylist(id);
      setPlaylists((prev) => prev.filter((p) => p.id !== id));
      if (selectedPlaylistId === id) {
        setSelectedPlaylistId(null);
        setSelectedPlaylistName("");
        setSelectedPlaylistTracks([]);
      }
      setStatus("Playlist eliminada");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No pudimos eliminar la playlist");
    } finally {
      setLibraryBusy(false);
    }
  }

  async function openPlaylist(id: string) {
    setPlaylistDetailBusy(true);
    setSelectedPlaylistId(id);
    try {
      const playlist = await getPlaylist(id);
      setSelectedPlaylistName(playlist?.name || "");
      setSelectedPlaylistVisibility((playlist?.visibility as "private" | "public") || "private");
      const rows = (await listPlaylistTracks(id)) || [];
      const sorted = [...rows].sort(
        (a, b) => (Number(a.position) || 0) - (Number(b.position) || 0),
      );
      const enriched = await enrichTrackIds(
        sorted
          .map((r) => ({
            trackId: String(r.track_id || ""),
            position: r.position,
            added_at: r.added_at,
          }))
          .filter((r) => r.trackId),
      );
      setSelectedPlaylistTracks(enriched);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No pudimos abrir la playlist");
      setSelectedPlaylistId(null);
    } finally {
      setPlaylistDetailBusy(false);
    }
  }

  async function savePlaylistName() {
    if (!editingPlaylistId) return;
    const name = playlistNameDraft.trim();
    if (!name) return;
    setLibraryBusy(true);
    try {
      await renamePlaylist(editingPlaylistId, name);
      setPlaylists((prev) => prev.map((p) => (p.id === editingPlaylistId ? { ...p, name } : p)));
      if (selectedPlaylistId === editingPlaylistId) setSelectedPlaylistName(name);
      setEditingPlaylistId(null);
      setPlaylistNameDraft("");
      setStatus("Nombre actualizado");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No pudimos renombrar");
    } finally {
      setLibraryBusy(false);
    }
  }

  async function removeTrackFromOpenPlaylist(trackId: string) {
    if (!selectedPlaylistId) return;
    try {
      await removeTrackFromPlaylist(selectedPlaylistId, trackId);
      setSelectedPlaylistTracks((prev) => prev.filter((t) => resolveTrackId(t) !== trackId));
      setStatus("Canción quitada de la playlist");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudo quitar");
    }
  }

  async function movePlaylistTrack(trackId: string, direction: -1 | 1) {
    if (!selectedPlaylistId) return;
    const ids = selectedPlaylistTracks.map(resolveTrackId);
    const index = ids.indexOf(trackId);
    if (index < 0) return;
    const target = index + direction;
    if (target < 0 || target >= ids.length) return;
    const next = [...ids];
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item);
    try {
      await reorderPlaylistTracks(selectedPlaylistId, next);
      const reordered = next
        .map((id) => selectedPlaylistTracks.find((t) => resolveTrackId(t) === id))
        .filter(Boolean);
      setSelectedPlaylistTracks(reordered as any[]);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudo reordenar");
    }
  }

  async function togglePlaylistVisibility() {
    if (!selectedPlaylistId) return;
    const nextVis = selectedPlaylistVisibility === "public" ? "private" : "public";
    try {
      await renamePlaylist(selectedPlaylistId, selectedPlaylistName, nextVis);
      setSelectedPlaylistVisibility(nextVis);
      setPlaylists((prev) =>
        prev.map((p) => (p.id === selectedPlaylistId ? { ...p, visibility: nextVis } : p)),
      );
      setStatus(nextVis === "public" ? "Playlist pública" : "Playlist privada");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudo cambiar visibilidad");
    }
  }

  async function sharePlaylist() {
    if (!selectedPlaylistId) return;
    if (selectedPlaylistVisibility !== "public") {
      setStatus("Haz pública la playlist antes de compartirla.");
      return;
    }
    const url = `${window.location.origin}/?playlist=${encodeURIComponent(selectedPlaylistId)}`;
    try {
      if (navigator.share) await navigator.share({ title: selectedPlaylistName || "KubanFy", url });
      else {
        await navigator.clipboard.writeText(url);
        setStatus("Enlace copiado");
      }
    } catch {
      /* cancelled */
    }
  }

  return (
    <section>
      <h2>Playlists</h2>
      <div className="playlist-create glass">
        <input
          value={newPlaylistName}
          onChange={(e) => setNewPlaylistName(e.target.value)}
          placeholder="Nombre de la nueva playlist"
          onKeyDown={(e) => {
            if (e.key === "Enter") void makePlaylist();
          }}
        />
        <button
          className="primary-button"
          disabled={libraryBusy || !newPlaylistName.trim()}
          onClick={() => void makePlaylist()}
        >
          Crear
        </button>
      </div>

      <div className="playlist-list">
        {playlists.map((pl: any) => (
          <div key={pl.id} className="playlist-card glass">
            {editingPlaylistId === pl.id ? (
              <div className="playlist-edit">
                <input
                  value={playlistNameDraft}
                  onChange={(e) => setPlaylistNameDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void savePlaylistName();
                    if (e.key === "Escape") setEditingPlaylistId(null);
                  }}
                  autoFocus
                />
                <button className="secondary-button" onClick={() => void savePlaylistName()}>
                  Guardar
                </button>
                <button className="icon-button" onClick={() => setEditingPlaylistId(null)} aria-label="Cancelar">
                  ×
                </button>
              </div>
            ) : (
              <>
                <button className="track-info" onClick={() => void openPlaylist(pl.id)}>
                  <strong>{pl.name}</strong>
                  <span>{pl.visibility === "public" ? "Pública" : "Privada"}</span>
                </button>
                <div className="playlist-card-actions">
                  <button
                    className="icon-button"
                    onClick={() => {
                      setEditingPlaylistId(pl.id);
                      setPlaylistNameDraft(pl.name || "");
                    }}
                    aria-label="Renombrar"
                  >
                    ✎
                  </button>
                  <button
                    className="icon-button"
                    disabled={libraryBusy}
                    onClick={() => void removePlaylist(pl.id)}
                    aria-label="Eliminar"
                  >
                    ×
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>

      {selectedPlaylistId && (
        <div className="playlist-detail glass">
          <div className="playlist-detail-heading">
            <div>
              <span className="eyebrow">PLAYLIST</span>
              <h2>{selectedPlaylistName || "Playlist"}</h2>
              <p>
                {selectedPlaylistTracks.length} canciones ·{" "}
                {selectedPlaylistVisibility === "public" ? "Pública" : "Privada"}
              </p>
            </div>
            <div className="playlist-detail-actions">
              <button
                className="primary-button"
                disabled={playlistDetailBusy || selectedPlaylistTracks.length === 0}
                onClick={() =>
                  void onPlay(
                    resolveTrackId(selectedPlaylistTracks[0]),
                    selectedPlaylistTracks.map(resolveTrackId),
                  )
                }
              >
                ▶ Reproducir todo
              </button>
              <button className="secondary-button" onClick={() => void togglePlaylistVisibility()}>
                {selectedPlaylistVisibility === "public" ? "Hacer privada" : "Hacer pública"}
              </button>
              <button className="secondary-button" onClick={() => void sharePlaylist()}>
                Compartir
              </button>
              <button
                className="icon-button"
                onClick={() => {
                  setSelectedPlaylistId(null);
                  setSelectedPlaylistName("");
                  setSelectedPlaylistTracks([]);
                }}
                aria-label="Cerrar playlist"
              >
                ×
              </button>
            </div>
          </div>

          {playlistDetailBusy ? (
            <div className="empty-state">Cargando canciones…</div>
          ) : selectedPlaylistTracks.length === 0 ? (
            <div className="empty-state">
              <strong>Esta playlist está vacía</strong>
              <span>Añade canciones desde Buscar o el reproductor.</span>
            </div>
          ) : (
            <div className="library-list">
              {selectedPlaylistTracks.map((track, index) => {
                const id = resolveTrackId(track);
                return (
                  <article key={id} className="glass library-track">
                    <button
                      className="track-info playlist-track-play"
                      onClick={() => void onPlay(id, selectedPlaylistTracks.map(resolveTrackId))}
                    >
                      <strong>{track.title || "Canción"}</strong>
                      <span>{trackArtistsLabel(track)}</span>
                    </button>
                    <button
                      className="icon-button"
                      onClick={() => void movePlaylistTrack(id, -1)}
                      disabled={index === 0}
                      aria-label="Subir"
                    >
                      ↑
                    </button>
                    <button
                      className="icon-button"
                      onClick={() => void movePlaylistTrack(id, 1)}
                      disabled={index === selectedPlaylistTracks.length - 1}
                      aria-label="Bajar"
                    >
                      ↓
                    </button>
                    <button
                      className="icon-button"
                      onClick={() => void removeTrackFromOpenPlaylist(id)}
                      aria-label="Quitar de playlist"
                    >
                      ×
                    </button>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      )}

      <h2>Favoritos</h2>
      {favorites.length === 0 ? (
        <div className="empty-state">
          <strong>Sin favoritos aún</strong>
          <span>Marca canciones con el corazón desde Buscar.</span>
        </div>
      ) : (
        <div className="library-list">
          {favorites.map((t: any) => {
            const id = resolveTrackId(t);
            return (
              <article key={id} className="glass library-track">
                <button className="track-info" onClick={() => void onPlay(id)}>
                  <strong>{t.title || "Canción"}</strong>
                  <span>{trackArtistsLabel(t)}</span>
                </button>
                <button
                  className={`icon-button favorite-button${favoriteIds.has(id) ? " is-active" : ""}`}
                  onClick={() => onToggleFavorite(id)}
                  aria-label="Quitar de favoritos"
                >
                  ♥
                </button>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
