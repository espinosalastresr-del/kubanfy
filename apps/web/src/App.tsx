import { useEffect, useRef, useState } from "react";
import { addFavorite, addTrackToPlaylist, clearTokens, discoveryHome, getTrackDetail, listFavorites, listMyEntitlements, listPlaylists, login, me, removeFavorite, searchTracks } from "./api";
import { KbyPlayer } from "./player";
import { QueueSheet } from "./QueueSheet";
import { buildDefaultQueue, mergeQueueMeta, trackArtistsLabel, type QueueTrackMeta } from "./queue";
import { LoginView } from "./LoginView";
import { RegisterView } from "./RegisterView";
import { LibraryPanel } from "./LibraryPanel";
import { OfflinePanel } from "./OfflinePanel";
import { getTrack as getOfflineTrack } from "./offlineDb";
import { subscribeConnectivity, isOnline } from "./connectivity";
import { applyServiceWorkerUpdate } from "./swRegister";
import { tierFromUser } from "./autoCache";
import { SettingsPanel } from "./SettingsPanel";
import { isDataSaverEnabled, resolveStreamingQuality } from "./dataSaver";
import type { PlanTier } from "./cachePolicy";
import { ForgotPasswordView } from "./ForgotPasswordView";
import { ResetPasswordView } from "./ResetPasswordView";
import { EmailVerificationView } from "./EmailVerificationView";
import { DiagnosticsPanel } from "./DiagnosticsPanel";
import { AccountPanel } from "./AccountPanel";
import { EntitlementsPanel } from "./EntitlementsPanel";
import { planTierFromEntitlements } from "./entitlements";
import { enrichTrackIds, resolveTrackId } from "./trackMeta";
import { enrollCurrentBrowserIdentity } from "./deviceIdentity";
import { getPreferredAudioQuality } from "./dataSaver";

function HeartIcon({ filled }: { filled: boolean }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 8.7c0 5.4-8.8 10.3-8.8 10.3S3.2 14.1 3.2 8.7A4.7 4.7 0 0 1 12 6.2a4.7 4.7 0 0 1 8.8 2.5Z" fill={filled ? "currentColor" : "none"} /></svg>;
}
function ShareIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.7 10.6 6.6-4.2M8.7 13.4l6.6 4.2"/></svg>; }
function PlusIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>; }
function QueueIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h10M4 18h10" /><path d="M16 15l4 3-4 3" /></svg>; }
function SearchIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 5 5" /></svg>; }
function LogoMark() { return <div className="logo-mark" aria-hidden="true"><span /><span /><span /></div>; }

function clearVerificationTokenFromUrl(): void {
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete("verify_token");
    const hashParams = new URLSearchParams(url.hash.replace(/^#/, ""));
    hashParams.delete("verify_token");
    url.hash = hashParams.toString();
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
  } catch {
    /* Ignore URL cleanup failures; verification state remains server-side. */
  }
}

export default function App() {
  const [user, setUser] = useState<any>(null);
  const [authMode, setAuthMode] = useState<"login" | "register" | "forgot" | "verify">("login");
  const [registeredEmail, setRegisteredEmail] = useState("");
  const [tab, setTab] = useState<"home" | "search" | "library">("home");
  const [status, setStatus] = useState("");
  const [online, setOnline] = useState(isOnline());
  const [swUpdate, setSwUpdate] = useState(false);
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
  const [queueMeta, setQueueMeta] = useState<Record<string, QueueTrackMeta>>({});
  const [queueOpen, setQueueOpen] = useState(false);
  const [playlistMenuTrack, setPlaylistMenuTrack] = useState<string | null>(null);
  const [planTier, setPlanTier] = useState<PlanTier>("free");
  const [dataSaver, setDataSaver] = useState(isDataSaverEnabled());
  const playerRef = useRef(new KbyPlayer());
  const player = playerRef.current;

  // Match the real /v1/discovery/home response. The API exposes trending,
  // new_releases and top_50_country (not the legacy featured/recent fields).
  const discoveryTracks = [
    ...(home?.trending || []),
    ...(home?.new_releases || []),
    ...(home?.top_50_country || []),
  ].filter((track: any, index: number, rows: any[]) => {
    const id = String(track?.track_id || track?.id || "");
    return id && rows.findIndex((row) => String(row?.track_id || row?.id || "") === id) === index;
  });

  const [verifyToken, setVerifyToken] = useState<string | null>(() => {
    try {
      const searchParams = new URLSearchParams(window.location.search);
      const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
      // Prefer the fragment for new links; retain query support for previously
      // issued verification emails.
      return hashParams.get("verify_token") || searchParams.get("verify_token");
    } catch {
      return null;
    }
  });

  const [resetToken, setResetToken] = useState<string | null>(() => {
    try {
      const searchParams = new URLSearchParams(window.location.search);
      // Password-reset links intentionally keep the bearer token in the URL
      // fragment so it is not sent in HTTP requests, access logs, or referrers.
      // Read both the fragment (current backend format) and query parameters
      // for compatibility with links already issued by older clients.
      const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
      return (
        searchParams.get("reset_token") ||
        searchParams.get("token") ||
        hashParams.get("reset_token") ||
        hashParams.get("token") ||
        null
      );
    } catch {
      return null;
    }
  });

  useEffect(() => {
    void (async () => {
      try {
        const u = await me();
        setUser(u);
        let tier = tierFromUser(u);
        try {
          const ents = await listMyEntitlements();
          tier = planTierFromEntitlements(ents);
        } catch {
          /* keep tierFromUser fallback */
        }
        setPlanTier(tier);
        player.setPlanTier(tier);
        void ensureBrowserIdentity();
      } catch {
        clearTokens();
        setPlanTier("guest");
        player.setPlanTier("guest");
      }
    })();
  }, []);

  useEffect(() => {
    setOnline(isOnline());
    const unsub = subscribeConnectivity(setOnline);
    const onUpd = () => setSwUpdate(true);
    const onSaver = () => setDataSaver(isDataSaverEnabled());
    window.addEventListener("kubanfy:sw-update", onUpd);
    window.addEventListener("kubanfy:data-saver", onSaver);
    return () => {
      unsub();
      window.removeEventListener("kubanfy:sw-update", onUpd);
      window.removeEventListener("kubanfy:data-saver", onSaver);
    };
  }, []);

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        setHome(await discoveryHome());
        setPlaylists(await listPlaylists());
        const favs = await listFavorites();
        const trackRows = favs
          .filter((f) => !f.target_type || f.target_type === "track")
          .map((f) => ({
            trackId: String(f.target_id || ""),
            favorite_id: f.id,
          }))
          .filter((r) => r.trackId);
        const enriched = await enrichTrackIds(trackRows);
        setFavorites(enriched);
        setFavoriteIds(new Set(enriched.map((t) => String(t.track_id || t.id))));
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

  async function ensureBrowserIdentity() {
    try {
      const result = await enrollCurrentBrowserIdentity();
      if (result === "unsupported") {
        setStatus("Este navegador no ofrece almacenamiento criptográfico compatible; la sesión seguirá funcionando con la protección habitual.");
      } else if (result === "recovery-required") {
        setStatus("La clave segura de este navegador ya no está disponible. Revoca este dispositivo desde Cuenta y vuelve a iniciar sesión para crear una identidad nueva.");
      }
    } catch (error) {
      setStatus(error instanceof Error
        ? `La sesión está activa, pero no se pudo verificar la identidad del navegador: ${error.message}`
        : "La sesión está activa, pero no se pudo verificar la identidad del navegador.");
    }
  }

  async function doLogin(email: string, password: string) {
    await login(email, password);
    const u = await me();
    setUser(u);
    let tier = tierFromUser(u);
    try {
      const ents = await listMyEntitlements();
      tier = planTierFromEntitlements(ents);
    } catch {
      /* fallback */
    }
    setPlanTier(tier);
    player.setPlanTier(tier);
    await ensureBrowserIdentity();
  }

  async function play(id: string, requestedQueue?: string[]) {
    try {
      setStatus("Cargando…");
      let metadata: any = { id, track_id: id, title: "Canción" };
      try {
        const detail = await getTrackDetail(id);
        if (detail) metadata = detail;
      } catch {
        try {
          const offline = await getOfflineTrack(id);
          if (offline) {
            metadata = {
              id,
              track_id: id,
              title: offline.title || "Canción",
              artwork_url: offline.artworkUrl || null,
              duration: offline.duration,
            };
          }
        } catch {
          /* ignore */
        }
      }
      const known = [...discoveryTracks, ...searchResults, ...favorites];
      const queue = requestedQueue?.length ? requestedQueue : buildDefaultQueue(id, known);
      setQueueIds(queue);
      setQueueMeta(prev => mergeQueueMeta(prev, [...known, metadata]));
      setActiveTrackId(id);
      setActiveTrack(metadata);
      player.setMetadata({
        title: metadata?.title || "Canción",
        artist: trackArtistsLabel(metadata) || "KubanFy",
        album: metadata?.album || undefined,
        artwork: metadata?.artwork_url || metadata?.artwork || null,
      });
      player.setTrackInfo({
        title: metadata?.title || "Canción",
        duration: metadata?.duration ?? null,
        artworkUrl: metadata?.artwork_url || metadata?.artwork || null,
      });
      const preferred = getPreferredAudioQuality();
      const q = resolveStreamingQuality(
        planTier,
        isDataSaverEnabled(),
        preferred === "low" ? "low" : "medium",
      );
      await player.playTrack(id, q);
      setStatus("");
      setPlayerExpanded(false);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudo reproducir");
    }
  }

  function playFromQueue(id: string) { void play(id, queueIds.length ? queueIds : [id]); }

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

  function clearQueueKeepingCurrent() {
    if (!activeTrackId) { setQueueIds([]); setQueueOpen(false); return; }
    setQueueIds([activeTrackId]);
  }

  function nextTrack(direction: 1 | -1) {
    if (!queueIds.length) return;
    if (queueIds.length === 1) { if (direction > 0 && activeTrackId) void play(activeTrackId, queueIds); return; }
    const base = activeTrackId ? queueIds.indexOf(activeTrackId) : 0;
    void play(queueIds[(base + direction + queueIds.length) % queueIds.length], queueIds);
  }

  async function toggleFavorite(trackId: string) {
    const was = favoriteIds.has(trackId);
    try {
      if (was) {
        await removeFavorite(trackId);
        setFavoriteIds(prev => { const n = new Set(prev); n.delete(trackId); return n; });
        setFavorites(prev => prev.filter(t => resolveTrackId(t) !== trackId));
        setStatus("Quitada de favoritos");
      } else {
        await addFavorite(trackId);
        setFavoriteIds(prev => new Set(prev).add(trackId));
        const detail = await getTrackDetail(trackId).catch(() => ({
          id: trackId,
          track_id: trackId,
          title: "Canción",
          duration: null,
          artists: [],
        }));
        setFavorites((prev) => [...prev, { ...detail, track_id: detail.id || trackId }]);
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
      else { await navigator.clipboard.writeText(url); setStatus("Enlace copiado"); }
    } catch { /* cancelled */ }
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

  if (resetToken) {
    return (
      <ResetPasswordView
        token={resetToken}
        onDone={() => {
          setResetToken(null);
          try {
            const u = new URL(window.location.href);
            u.searchParams.delete("reset_token");
            u.searchParams.delete("token");
            window.history.replaceState({}, "", u.pathname + u.search);
          } catch { /* ignore */ }
          setAuthMode("login");
        }}
      />
    );
  }

  if (verifyToken) {
    return (
      <EmailVerificationView
        initialEmail={registeredEmail}
        token={verifyToken}
        onBack={() => {
          setVerifyToken(null);
          clearVerificationTokenFromUrl();
          setAuthMode("login");
        }}
        onVerified={() => {
          setVerifyToken(null);
          clearVerificationTokenFromUrl();
          setAuthMode("login");
        }}
      />
    );
  }

  if (!user) {
    if (authMode === "verify") {
      return (
        <EmailVerificationView
          initialEmail={registeredEmail}
          token={null}
          onBack={() => setAuthMode("login")}
          onVerified={() => setAuthMode("login")}
        />
      );
    }
    if (authMode === "register") {
      return <RegisterView onBack={() => setAuthMode("login")} onRegistered={(email) => { setRegisteredEmail(email); setAuthMode("verify"); }} />;
    }
    if (authMode === "forgot") {
      return <ForgotPasswordView initialEmail={registeredEmail} onBack={() => setAuthMode("login")} />;
    }
    return (
      <LoginView
        onLogin={doLogin}
        onRegister={() => setAuthMode("register")}
        onForgot={() => setAuthMode("forgot")}
        onVerifyEmail={(email) => { setRegisteredEmail(email); setAuthMode("verify"); }}
        initialEmail={registeredEmail}
      />
    );
  }

  const tracksHome = discoveryTracks;

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

      {status && <p className="status-banner">{status}</p>}
      {!online && (
        <p className="status-banner" style={{ background: "rgba(255,180,80,.15)", color: "var(--accent-2, #f0c674)" }}>
          Sin conexión — puedes reproducir descargas offline listas
        </p>
      )}
      {swUpdate && (
        <p className="status-banner" style={{ background: "rgba(141,225,208,.12)", color: "var(--accent-2)" }}>
          Nueva versión disponible{" "}
          <button className="secondary-button" style={{ marginLeft: 8 }} onClick={() => applyServiceWorkerUpdate()}>
            Actualizar
          </button>
        </p>
      )}

      <main className="main-scroll">
        {tab === "home" && (
          <section className="home-section">
            <h2>Para ti</h2>
            <div className="track-grid">
              {tracksHome.map((t: any) => {
                const id = String(t?.track_id || t?.id || "");
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

        {tab === "search" && (
          <section className="search-section">
            <div className="search-bar glass">
              <SearchIcon />
              <input
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    void (async () => {
                      try {
                        setSearchResults(await searchTracks(searchQ));
                      } catch (err) {
                        setStatus(err instanceof Error ? err.message : "Búsqueda falló");
                      }
                    })();
                  }
                }}
                placeholder="Buscar canciones…"
              />
            </div>
            <div className="track-grid">
              {searchResults.map((t: any) => {
                const id = String(t?.track_id || t?.id || "");
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
          <>
            <LibraryPanel
              playlists={playlists}
              setPlaylists={setPlaylists}
              favorites={favorites}
              favoriteIds={favoriteIds}
              onToggleFavorite={(id) => void toggleFavorite(id)}
              onPlay={(id, queue) => void play(id, queue)}
              setStatus={setStatus}
            />
            <OfflinePanel setStatus={setStatus} onPlayOnline={(id) => void play(id)} />
            <SettingsPanel tier={planTier} setStatus={setStatus} />
            <DiagnosticsPanel tier={planTier} setStatus={setStatus} />
            <AccountPanel
              user={user}
              setUser={setUser}
              setStatus={setStatus}
              onLoggedOut={() => {
                clearTokens();
                setUser(null);
              }}
            />
            <EntitlementsPanel
              tier={planTier}
              setStatus={setStatus}
              onTierResolved={(t) => {
                setPlanTier(t);
                player.setPlanTier(t);
              }}
            />
          </>
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
            <button className="icon-button" onClick={() => nextTrack(-1)} aria-label="Anterior" disabled={queueIds.length === 0}>|◀</button>
            <button className="icon-button primary" onClick={() => player.togglePlayback()} aria-label={isPlaying ? "Pausa" : "Play"}>{isPlaying ? "❚❚" : "▶"}</button>
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
              <span>Reproduciendo en KubanFy{dataSaver ? " · Ahorro de datos" : ""}</span>
              <strong>{activeTrack?.title}</strong>
              <span>{activeTrack?.album || "Tu música, a tu manera"}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
