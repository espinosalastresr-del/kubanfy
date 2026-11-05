import { useEffect, useRef, useState } from "react";
import { clearTokens, discoveryHome, getTrackDetail, listFavorites, listPlaylists, listPlaylistTracks, login, me, searchTracks, addTrackToPlaylist } from "./api";
import { KbyPlayer } from "./player";
import { QueueSheet } from "./QueueSheet";
import { buildDefaultQueue, mergeQueueMeta, trackArtistsLabel, type QueueTrackMeta } from "./queue";
import { LoginView } from "./LoginView";
import { RegisterView } from "./RegisterView";

function QueueIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h10M4 18h10" /><path d="M16 15l4 3-4 3" /></svg>;
}
function LogoMark() {
  return <div className="logo-mark" aria-hidden="true"><span /><span /><span /></div>;
}

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
  const [playlistTracks, setPlaylistTracks] = useState<any[]>([]);
  const [selectedPlaylist, setSelectedPlaylist] = useState<any>(null);
  const [activeTrackId, setActiveTrackId] = useState<string | null>(null);
  const [activeTrack, setActiveTrack] = useState<any>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [queueIds, setQueueIds] = useState<string[]>([]);
  const [queueOpen, setQueueOpen] = useState(false);
  const [queueMeta, setQueueMeta] = useState<Record<string, QueueTrackMeta>>({});
  const playerRef = useRef<KbyPlayer | null>(null);
  if (!playerRef.current) playerRef.current = new KbyPlayer();
  const player = playerRef.current;

  useEffect(() => { void me().then(setUser).catch(() => setUser(null)); }, []);
  useEffect(() => {
    if (!user) return;
    void Promise.all([discoveryHome(), listPlaylists(), listFavorites()])
      .then(([h, pls, favs]) => { setHome(h); setPlaylists(pls || []); setFavorites(favs || []); })
      .catch(e => setStatus(String(e)));
  }, [user]);
  useEffect(() => {
    player.onPlayState = (p: boolean) => setIsPlaying(p);
    player.onEnded = () => nextTrack(1);
    player.onNext = () => nextTrack(1);
    player.onPrevious = () => nextTrack(-1);
  });

  async function play(id: string, requestedQueue?: string[]) {
    try {
      setStatus("Cargando…");
      const detail = await getTrackDetail(id);
      const metadata = detail || { id, track_id: id, title: "Canción" };
      const known = [...(home?.featured || []), ...(home?.recent || []), ...searchResults, ...favorites, ...playlistTracks];
      const queue = requestedQueue?.length ? requestedQueue : buildDefaultQueue(id, known);
      setQueueIds(queue);
      setQueueMeta(prev => mergeQueueMeta(prev, [...known, metadata]));
      setActiveTrackId(id);
      setActiveTrack(metadata);
      await player.playTrack(id);
      setStatus("");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudo reproducir");
    }
  }

  function nextTrack(direction: 1 | -1) {
    if (!queueIds.length) return;
    if (queueIds.length === 1) { if (direction > 0 && activeTrackId) void play(activeTrackId, queueIds); return; }
    const index = activeTrackId ? queueIds.indexOf(activeTrackId) : -1;
    const nextIndex = ((index >= 0 ? index : 0) + direction + queueIds.length) % queueIds.length;
    void play(queueIds[nextIndex], queueIds);
  }

  function removeFromQueue(id: string) {
    setQueueIds(prev => {
      const next = prev.filter(x => x !== id);
      if (id === activeTrackId) {
        if (next.length) void play(next[0], next);
        else { player.stop(); setActiveTrackId(null); setActiveTrack(null); setQueueOpen(false); }
      }
      return next;
    });
  }

  if (!user) {
    if (authMode === "register") {
      return <RegisterView onBack={() => setAuthMode("login")} onRegistered={email => { setRegisteredEmail(email); setAuthMode("login"); }} />;
    }
    return <LoginView onLogin={async (email, password) => { await login(email, password); setUser(await me()); }} onRegister={() => setAuthMode("register")} initialEmail={registeredEmail} />;
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
        <button className="icon-button" onClick={() => { clearTokens(); setUser(null); }} aria-label="Salir">⎋</button>
      </header>
      <main className="content">
        {status && <p className="status-banner">{status}</p>}
        {tab === "home" && (
          <section>
            <h2>Para ti</h2>
            <div className="track-grid">
              {tracksHome.map((t: any) => {
                const id = t.track_id || t.id;
                return <button key={id} className="track-card glass" onClick={() => void play(id)}><strong>{t.title || "Canción"}</strong><small>{trackArtistsLabel(t)}</small></button>;
              })}
            </div>
          </section>
        )}
        {tab === "search" && (
          <section>
            <input className="search-input" value={searchQ} onChange={e => setSearchQ(e.target.value)} placeholder="Buscar"
              onKeyDown={e => { if (e.key === "Enter") void searchTracks(searchQ).then(setSearchResults).catch(err => setStatus(String(err))); }} />
            <div className="track-grid">
              {searchResults.map((t: any) => {
                const id = t.track_id || t.id;
                return <button key={id} className="track-card glass" onClick={() => void play(id)}><strong>{t.title}</strong><small>{trackArtistsLabel(t)}</small></button>;
              })}
            </div>
          </section>
        )}
        {tab === "library" && (
          <section>
            <h2>Playlists</h2>
            {playlists.map((pl: any) => (
              <button key={pl.id} className="playlist-card glass" onClick={() => void listPlaylistTracks(pl.id).then(tr => { setSelectedPlaylist(pl); setPlaylistTracks(tr || []); })}>
                <strong>{pl.name}</strong>
              </button>
            ))}
            {selectedPlaylist && playlistTracks.map((t: any) => {
              const id = t.track_id || t.id;
              return <button key={id} className="track-row" onClick={() => void play(id, playlistTracks.map((x: any) => x.track_id || x.id))}>{t.title}</button>;
            })}
            <h2>Favoritos</h2>
            {favorites.map((t: any) => {
              const id = t.track_id || t.id;
              return <button key={id} className="track-row" onClick={() => void play(id)}>{t.title}</button>;
            })}
          </section>
        )}
      </main>
      {activeTrackId && (
        <div className="player glass">
          <div className="player-meta">
            <strong>{activeTrack?.title || "Canción"}</strong>
            <small>{trackArtistsLabel(activeTrack)}</small>
          </div>
          <div className="player-controls">
            <button className="icon-button" onClick={() => nextTrack(-1)} aria-label="Anterior" disabled={queueIds.length < 2}>|◀</button>
            <button className="play-button" onClick={() => { const r = player.togglePlayback(); if (r instanceof Promise) void r.catch(() => setStatus("Pulsa reproducir")); }} aria-label={isPlaying ? "Pausar" : "Reproducir"}>{isPlaying ? "Ⅱ" : "▶"}</button>
            <button className="icon-button" onClick={() => nextTrack(1)} aria-label="Siguiente" disabled={!queueIds.length}>▶|</button>
            <button className={`icon-button${queueOpen ? " is-active" : ""}`} onClick={() => setQueueOpen(v => !v)} aria-label={queueOpen ? "Cerrar cola" : "Abrir cola"} aria-expanded={queueOpen}><QueueIcon /></button>
            <button className="player-close" onClick={() => { player.stop(); setActiveTrackId(null); setActiveTrack(null); setQueueOpen(false); }} aria-label="Cerrar">×</button>
          </div>
          {queueOpen && (
            <QueueSheet
              queueIds={queueIds}
              activeTrackId={activeTrackId}
              isPlaying={isPlaying}
              queueMeta={queueMeta}
              activeTrack={activeTrack}
              onPlay={id => void play(id, queueIds)}
              onRemove={removeFromQueue}
              onClearKeepCurrent={() => activeTrackId && setQueueIds([activeTrackId])}
              onClose={() => setQueueOpen(false)}
            />
          )}
        </div>
      )}
    </div>
  );
}
