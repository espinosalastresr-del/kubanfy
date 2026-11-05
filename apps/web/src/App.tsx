import { FormEvent, useEffect, useRef, useState } from "react";
import { ApiError, addFavorite, addTrackToPlaylist, clearTokens, createPlaylist, deletePlaylist, discoveryHome, getPlaylist, getTrackDetail, listFavorites, listPlaylistTracks, listPlaylists, login, me, register, removeFavorite, removeTrackFromPlaylist, renamePlaylist, reorderPlaylistTracks, searchTracks } from "./api";
import { KbyPlayer } from "./player";
import { QueueSheet } from "./QueueSheet";
import { buildDefaultQueue, mergeQueueMeta, trackArtistsLabel, type QueueTrackMeta } from "./queue";
import { LoginView } from "./LoginView";
import { RegisterView } from "./RegisterView";
import { LibraryPanel } from "./LibraryPanel";

function HeartIcon({ filled }: { filled: boolean }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 8.7c0 5.4-8.8 10.3-8.8 10.3S3.2 14.1 3.2 8.7A4.7 4.7 0 0 1 12 6.2a4.7 4.7 0 0 1 8.8 2.5Z" fill={filled ? "currentColor" : "none"} /></svg>;
}
function ShareIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.7 10.6 6.6-4.2M8.7 13.4l6.6 4.2"/></svg>; }
function PlusIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>; }
function QueueIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h10M4 18h10" /><path d="M16 15l4 3-4 3" /></svg>; }
function SearchIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 5 5" /></svg>; }
function LogoMark() { return <div className="logo-mark" aria-hidden="true"><span /><span /><span /></div>; }

export default function App() {
  const [user, setUser] = useState<any>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [registeredEmail, setRegisteredEmail] = useState("");
  const [tab, setTab] = useState<"home" | "search" | "library">("home");
  const [status, setStatus] = useState("");
  const [home, setHome] = useState<any>(null);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [playlists, setPlaylists] = useState<any[]>([]);
  const [favorites, setFavorites] = useState<any[]>([]);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());
  const [activeTrackId, setActiveTrackId] = useState<string | null>(null);
  const [activeTrack, setActiveTrack] = useState<any>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playerExpanded, setPlayerExpanded] = useState(false);
  const [queueIds, setQueueIds] = useState<string[]>([]);
  const [queueOpen, setQueueOpen] = useState(false);
  const [queueMeta, setQueueMeta] = useState<Record<string, QueueTrackMeta>>({});
  const [playlistMenuTrack, setPlaylistMenuTrack] = useState<string | null>(null);
  const playerRef = useRef<KbyPlayer | null>(null);
  if (!playerRef.current) playerRef.current = new KbyPlayer();
  const player = playerRef.current;

  useEffect(() => {
    void (async () => {
      try {
        const u = await me();
        setUser(u);
      } catch {
        setUser(null);
      }
    })();
  }, []);

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        const [h, pls, favs] = await Promise.all([discoveryHome(), listPlaylists(), listFavorites()]);
        setHome(h);
        setPlaylists(pls || []);
        setFavorites(favs || []);
        setFavoriteIds(new Set((favs || []).map((t: any) => String(t?.track_id || t?.id || "")).filter(Boolean)));
      } catch (e) {
        setStatus(e instanceof Error ? e.message : "Error al cargar");
      }
    })();
  }, [user]);

  useEffect(() => {
    player.onPlayState = (playing: boolean) => setIsPlaying(playing);
    player.onEnded = () => nextTrack(1);
    player.onNext = () => nextTrack(1);
    player.onPrevious = () => nextTrack(-1);
  });

  async function doLogin(email: string, password: string) {
    await login(email, password);
    const u = await me();
    setUser(u);
  }

  async function play(id: string, requestedQueue?: string[]) {
    try {
      setStatus("Cargando…");
      const detail = await getTrackDetail(id);
      const metadata = detail || { id, track_id: id, title: "Canción" };
      const known = [
        ...(home?.featured || []),
        ...(home?.recent || []),
        ...searchResults,
        ...favorites,
      ];
      const queue = requestedQueue?.length ? requestedQueue : buildDefaultQueue(id, known);
      setQueueIds(queue);
      setQueueMeta(prev => mergeQueueMeta(prev, known));
      setActiveTrackId(id);
      setActiveTrack(metadata);
      setQueueMeta(prev => mergeQueueMeta(prev, [metadata]));
      await player.playTrack(id);
      setStatus("");
      setPlayerExpanded(false);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudo reproducir");
    }
  }

  function playFromQueue(id: string) {
    void play(id, queueIds.length ? queueIds : [id]);
  }

  function removeFromQueue(id: string) {
    setQueueIds(prev => {
      const next = prev.filter(x => x !== id);
      if (id === activeTrackId) {
        if (next.length) void play(next[0], next);
        else {
          player.stop();
          setActiveTrackId(null);
          setActiveTrack(null);
          setQueueOpen(false);
        }
      }
      return next;
    });
  }

  function clearQueueKeepingCurrent() {
    if (!activeTrackId) {
      setQueueIds([]);
      setQueueOpen(false);
      return;
    }
    setQueueIds([activeTrackId]);
  }

  function nextTrack(direction: 1 | -1) {
    if (!queueIds.length) return;
    if (queueIds.length === 1) {
      if (direction > 0 && activeTrackId) void play(activeTrackId, queueIds);
      return;
    }
    const index = activeTrackId ? queueIds.indexOf(activeTrackId) : -1;
    const base = index >= 0 ? index : 0;
    const nextIndex = (base + direction + queueIds.length) % queueIds.length;
    void play(queueIds[nextIndex], queueIds);
  }

  async function toggleFavorite(trackId: string) {
    if (!trackId) return;
    const was = favoriteIds.has(trackId);
    try {
      if (was) {
        await removeFavorite(trackId);
        setFavoriteIds(prev => { const n = new Set(prev); n.delete(trackId); return n; });
        setFavorites(prev => prev.filter(t => String(t?.track_id || t?.id || "") !== trackId));
        setStatus("Quitada de favoritos");
      } else {
        await addFavorite(trackId);
        setFavoriteIds(prev => new Set(prev).add(trackId));
        const detail = await getTrackDetail(trackId).catch(() => ({ id: trackId, track_id: trackId, title: "Canción" }));
        setFavorites(prev => [...prev, detail]);
        setStatus("Añadida a favoritos");
      }
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudo actualizar favoritos");
    }
  }

  async function shareLink(title: string, path: string) {
    const url = `${window.location.origin}${path}`;
    try {
      if (navigator.share) await navigator.share({ title, url });
      else {
        await navigator.clipboard.writeText(url);
        setStatus("Enlace copiado");
      }
    } catch { /* user cancelled */ }
  }

  async function saveToPlaylist(playlistId: string, trackId: string) {
    try {
      await addTrackToPlaylist(playlistId, trackId);
      setPlaylistMenuTrack(null);
      setStatus("Añadida a la playlist");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudo añadir");
    }
  }

  if (!user) {
    if (authMode === "register") {
      return <RegisterView onBack={() => setAuthMode("login")} onRegistered={(email) => { setRegisteredEmail(email); setAuthMode("login"); }} />;
    }
    return <LoginView onLogin={doLogin} onRegister={() => setAuthMode("register")} initialEmail={registeredEmail} />;
  }

  const tracksHome = [...(home?.featured || []), ...(home?.recent || [])];

  return (
    <div className="app-shell">
      <header className="topbar glass">
        <div className="brand-lockup"><LogoMark /><span>KubanFy</span></div>
        <nav className="tabs">
          <button className={tab === "home" ? "is-active" : ""} onClick={() => setTab("home")}>Inicio</button>
          <button className={tab === "search" ? "is-active" : ""} onClick={() => setTab("search")}>Buscar</button>
          <button className={tab === "library" ? "is-active" : ""} onClick={() => setTab("library")}>Biblioteca</button>
        </nav>
        <button className="icon-button" onClick={() => { clearTokens(); setUser(null); }} aria-label="Cerrar sesión">⎋</button>
      </header>

      <main className="content">
        {status && <p className="status-banner">{status}</p>}

        {tab === "home" && (
          <section>
            <h2>Para ti</h2>
            <div className="track-grid">
              {tracksHome.map((t: any) => {
                const id = t.track_id || t.id;
                return (
                  <button key={id} className="track-card glass" onClick={() => void play(id)}>
                    <strong>{t.title || "Canción"}</strong>
                    <small>{trackArtistsLabel(t)}</small>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {tab === "search" && (
          <section>
            <div className="search-input">
              <SearchIcon />
              <input value={searchQ} onChange={e => setSearchQ(e.target.value)} placeholder="Buscar canciones"
                onKeyDown={e => { if (e.key === "Enter") void searchTracks(searchQ).then(setSearchResults).catch(err => setStatus(String(err))); }} />
            </div>
            <div className="track-grid">
              {searchResults.map((t: any) => {
                const id = t.track_id || t.id;
                return (
                  <button key={id} className="track-card glass" onClick={() => void play(id)}>
                    <strong>{t.title}</strong>
                    <small>{trackArtistsLabel(t)}</small>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {tab === "library" && (
          <LibraryPanel
            playlists={playlists}
            setPlaylists={setPlaylists}
            favorites={favorites}
            favoriteIds={favoriteIds}
            onToggleFavorite={(id) => void toggleFavorite(id)}
            onPlay={(id, queue) => void play(id, queue)}
            setStatus={setStatus}
          />
        )}
      </main>

      {activeTrackId && (
        <div className={`player glass${playerExpanded ? " is-expanded" : ""}`}>
          <button className="player-art" onClick={() => setPlayerExpanded(v => !v)} aria-label="Expandir">♪</button>
          <div className="player-meta" onClick={() => setPlayerExpanded(v => !v)}>
            <strong>{activeTrack?.title || "Canción"}</strong>
            <small>{trackArtistsLabel(activeTrack)}</small>
          </div>
          <div className="player-controls">
            <button className="icon-button" onClick={() => nextTrack(-1)} aria-label="Anterior" disabled={queueIds.length < 2}>|◀</button>
            <button className="play-button" onClick={() => { const r = player.togglePlayback(); if (r instanceof Promise) void r.catch(() => setStatus("Pulsa reproducir")); }} aria-label={isPlaying ? "Pausar" : "Reproducir"}>{isPlaying ? "Ⅱ" : "▶"}</button>
            <button className="icon-button" onClick={() => nextTrack(1)} aria-label="Siguiente" disabled={queueIds.length === 0}>▶|</button>
            <button className={`icon-button${queueOpen ? " is-active" : ""}`} onClick={() => { setQueueOpen(v => !v); setPlaylistMenuTrack(null); }} aria-label={queueOpen ? "Cerrar cola" : "Abrir cola"} aria-expanded={queueOpen}><QueueIcon /></button>
            <button className={`icon-button favorite-button${favoriteIds.has(activeTrackId) ? " is-active" : ""}`} onClick={() => void toggleFavorite(activeTrackId)} aria-label={favoriteIds.has(activeTrackId) ? "Quitar de favoritos" : "Añadir a favoritos"}><HeartIcon filled={favoriteIds.has(activeTrackId)} /></button>
            <button className="icon-button" onClick={() => setPlaylistMenuTrack(playlistMenuTrack === activeTrackId ? null : activeTrackId)} aria-label="Añadir a playlist"><PlusIcon /></button>
            <button className="icon-button" onClick={() => void shareLink(activeTrack?.title || "KubanFy", `/?track=${encodeURIComponent(activeTrackId)}`)} aria-label="Compartir"><ShareIcon /></button>
            <button className="player-close" onClick={() => { player.stop(); setActiveTrackId(null); setActiveTrack(null); setQueueOpen(false); }} aria-label="Cerrar">×</button>
          </div>
          {playlistMenuTrack === activeTrackId && (
            <div className="playlist-popover player-playlist-popover glass">
              {playlists.length === 0 ? <span>Crea una playlist en Biblioteca.</span> : playlists.map(pl => (
                <button key={pl.id} onClick={() => void saveToPlaylist(pl.id, activeTrackId)}>{pl.name}</button>
              ))}
            </div>
          )}
          {queueOpen && (
            <QueueSheet
              queueIds={queueIds}
              activeTrackId={activeTrackId}
              isPlaying={isPlaying}
              queueMeta={queueMeta}
              activeTrack={activeTrack}
              onPlay={playFromQueue}
              onRemove={removeFromQueue}
              onClearKeepCurrent={clearQueueKeepingCurrent}
              onClose={() => setQueueOpen(false)}
            />
          )}
          {playerExpanded && !queueOpen && (
            <div className="player-expanded-details">
              <span>Reproduciendo en KubanFy</span>
              <strong>{activeTrack?.title}</strong>
              <span>{activeTrack?.album || "Tu música, a tu manera"}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
