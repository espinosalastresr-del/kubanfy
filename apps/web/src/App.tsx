import { FormEvent, useEffect, useRef, useState } from "react";
import { ApiError, addFavorite, addTrackToPlaylist, clearTokens, createPlaylist, deletePlaylist, discoveryHome, listFavorites, listPlaylists, login, me, register, removeFavorite, searchTracks } from "./api";
import { KbyPlayer } from "./player";

function EyeIcon({ hidden }: { hidden: boolean }) {
  return hidden ? (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.7a2 2 0 0 0 2.7 2.7M9.9 5.2A10.8 10.8 0 0 1 12 5c5 0 8.5 4.1 9.5 6a17.7 17.7 0 0 1-3.1 3.7M6.2 6.2C3.9 7.7 2.5 10 2.5 12c1 1.9 4.5 6 9.5 6 1.7 0 3.2-.4 4.5-1.1" /></svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12S6 6 12 6s9.5 6 9.5 6S18 18 12 18s-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.8" /></svg>
  );
}

function HeartIcon({ filled }: { filled: boolean }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 8.7c0 5.4-8.8 10.3-8.8 10.3S3.2 14.1 3.2 8.7A4.7 4.7 0 0 1 12 6.2a4.7 4.7 0 0 1 8.8 2.5Z" fill={filled ? "currentColor" : "none"} /></svg>;
}
function LibraryIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4v16M10 4v16M15 4v16M19 7v10" /><path d="M3 4h15M3 20h15" /></svg>;
}
function PlusIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>;
}

function SearchIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 5 5" /></svg>;
}

function LogoMark() {
  return <div className="logo-mark" aria-hidden="true"><span /><span /><span /></div>;
}

function LoginView({ onLogin, onRegister, initialEmail }: { onLogin: (email: string, password: string) => Promise<void>; onRegister: () => void; initialEmail: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [notice, setNotice] = useState("");
  const [authError, setAuthError] = useState("");
  
  useEffect(() => {
    setEmail(initialEmail);
  }, [initialEmail]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    setAuthError("");
    if (!email || !password || !email.includes("@")) return;
    setBusy(true);
    try {
      await onLogin(email.trim(), password);
    } catch (e) {
      const message = e instanceof Error ? e.message : "";
      const status = e instanceof ApiError ? e.status : 0;
      if (status === 401 && /invalid email or password/i.test(message)) {
        setAuthError("El correo o la contraseña no son correctos. Comprueba tus datos e inténtalo de nuevo.");
      } else if (status === 401 && /suspended/i.test(message)) {
        setAuthError("Tu cuenta está suspendida. No puedes iniciar sesión mientras esta restricción esté activa.");
      } else if (status === 403 && /suspended/i.test(message)) {
        setAuthError("Tu cuenta está suspendida. Si crees que es un error, contacta con soporte.");
      } else if (status === 403 && e instanceof ApiError && e.code === "FORBIDDEN") {
        setAuthError("El servidor rechazó el inicio de sesión. Tu cuenta o esta sesión no tiene permiso para acceder ahora mismo.");
      } else if (status === 403 && e instanceof ApiError && e.code === "RIGHTS_ERROR") {
        setAuthError("El acceso de esta cuenta está restringido por sus permisos. Contacta con soporte si esto no debería ocurrir.");
      } else if (status === 429) {
        const retry = e instanceof ApiError && typeof e.details.retry_after === "number" ? e.details.retry_after : 0;
        setAuthError(retry > 0
          ? `Demasiados intentos. Espera aproximadamente ${Math.ceil(retry / 60)} minuto(s) antes de volver a intentarlo.`
          : "Demasiados intentos. Espera unos minutos antes de volver a intentarlo.");
      } else if (status === 404 || /account not found/i.test(message)) {
        setAuthError("No encontramos una cuenta con ese correo. Comprueba la dirección o crea una cuenta nueva.");
      } else if (!navigator.onLine || /failed to fetch|networkerror|load failed/i.test(message)) {
        setAuthError("No pudimos conectar con KubanFy. Comprueba tu conexión e inténtalo de nuevo.");
      } else if (e instanceof ApiError && e.requestId) {
        setAuthError(`KubanFy rechazó la solicitud (código ${e.code}). Inténtalo de nuevo. Si persiste, soporte puede localizarla con el ID ${e.requestId.slice(0, 8)}.`);
      } else {
        setAuthError("KubanFy no pudo completar el inicio de sesión. Inténtalo de nuevo en unos segundos.");
      }
    } finally {
      setBusy(false);
    }
  }

  return <main className="auth-page">
    <div className="ambient ambient-one" />
    <div className="ambient ambient-two" />
    <section className="auth-shell">
      <div className="auth-brand">
        <LogoMark />
        <span>KubanFy</span>
      </div>

      <div className="glass auth-card">
        <div className="auth-heading">
          <span className="eyebrow">TU MÚSICA. TU RITMO.</span>
          <h1>La música cubana, <em>contigo.</em></h1>
          <p>Escucha tus canciones favoritas incluso cuando la conexión no acompaña.</p>
        </div>

        <form onSubmit={submit} noValidate>
          <label className="field">
            <span>Correo electrónico</span>
            <input
              type="email"
              inputMode="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="tu@email.com"
              aria-invalid={submitted && (!email || !email.includes("@"))}
              required
            />
            {submitted && (!email || !email.includes("@")) && <small>Introduce un correo electrónico válido.</small>}
          </label>

          <label className="field">
            <span>Contraseña</span>
            <div className="password-field">
              <input
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Tu contraseña"
                aria-invalid={submitted && !password}
                required
              />
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowPassword(v => !v)}
                aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
              ><EyeIcon hidden={showPassword} /></button>
            </div>
            {submitted && !password && <small>Introduce tu contraseña.</small>}
          </label>

          <div className="form-meta">
            <a href="#recuperar" onClick={e => { e.preventDefault(); setNotice("La recuperación de contraseña estará disponible próximamente."); }}>¿Olvidaste tu contraseña?</a>
          </div>

          {notice && <div className="form-notice" role="status">{notice}</div>}
          {authError && <div className="form-status" role="alert" aria-live="assertive">{authError}</div>}

          <button className={`primary-button login-button${busy ? " is-loading" : ""}`} type="submit" disabled={busy} aria-busy={busy}>
            {busy ? (
              <>
                <span className="button-spinner" aria-hidden="true" />
                <span>Entrando…</span>
              </>
            ) : (
              <>
                <span>Entrar</span>
                <span className="button-arrow">→</span>
              </>
            )}
          </button>
        </form>

        <div className="auth-divider"><span>o</span></div>

        <p className="signup-prompt">¿Todavía no tienes cuenta? <a href="#registro" onClick={e => { e.preventDefault(); onRegister(); }}>Crear cuenta</a></p>
      </div>

      <p className="auth-footnote">KubanFy está diseñado para consumir menos datos y seguir sonando.</p>
    </section>
  </main>;
}

function RegisterView({ onBack, onRegistered }: { onBack: () => void; onRegistered: (email: string) => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    setError("");
    if (!name.trim() || !email.includes("@") || password.length < 8 || password !== confirmation) return;
    setBusy(true);
    try {
      await register(email.trim(), password, name.trim());
      onRegistered(email.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : "No pudimos crear la cuenta.");
    } finally {
      setBusy(false);
    }
  }

  return <main className="auth-page">
    <div className="ambient ambient-one" />
    <div className="ambient ambient-two" />
    <section className="auth-shell">
      <div className="auth-brand"><LogoMark /><span>KubanFy</span></div>
      <div className="glass auth-card">
        <div className="auth-heading">
          <span className="eyebrow">ÚNETE A KUBANFY</span>
          <h1>Crea tu <em>cuenta.</em></h1>
          <p>Empieza a escuchar música cubana pensada para conexiones reales.</p>
        </div>
        <form onSubmit={submit} noValidate>
          <label className="field">
            <span>Nombre</span>
            <input type="text" autoComplete="name" value={name} onChange={e => setName(e.target.value)} placeholder="Tu nombre" required />
            {submitted && !name.trim() && <small>Introduce tu nombre.</small>}
          </label>
          <label className="field">
            <span>Correo electrónico</span>
            <input type="email" inputMode="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="tu@email.com" required />
            {submitted && !email.includes("@") && <small>Introduce un correo electrónico válido.</small>}
          </label>
          <label className="field">
            <span>Contraseña</span>
            <div className="password-field">
              <input type={showPassword ? "text" : "password"} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Mínimo 8 caracteres" required />
              <button type="button" className="icon-button" onClick={() => setShowPassword(v => !v)} aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}><EyeIcon hidden={showPassword} /></button>
            </div>
            {submitted && password.length < 8 && <small>La contraseña debe tener al menos 8 caracteres.</small>}
          </label>
          <label className="field">
            <span>Repetir contraseña</span>
            <input type={showPassword ? "text" : "password"} autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} placeholder="Repite tu contraseña" required />
            {submitted && password !== confirmation && <small>Las contraseñas no coinciden.</small>}
          </label>
          {error && <div className="form-status" role="alert">{error}</div>}
          <button className={`primary-button login-button${busy ? " is-loading" : ""}`} type="submit" disabled={busy} aria-busy={busy}>
            {busy ? <><span className="button-spinner" aria-hidden="true" /><span>Creando cuenta…</span></> : <><span>Crear cuenta</span><span className="button-arrow">→</span></>}
          </button>
        </form>
        <div className="auth-divider"><span>o</span></div>
        <p className="signup-prompt"><a href="#login" onClick={e => { e.preventDefault(); onBack(); }}>← Volver a iniciar sesión</a></p>
      </div>
      <p className="auth-footnote">Tu cuenta queda protegida por la autenticación de KubanFy.</p>
    </section>
  </main>;
}

function formatDuration(seconds: number | null | undefined) {
  if (!seconds || seconds < 0) return "—";
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

export default function App() {
  const [user, setUser] = useState<unknown>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [registeredEmail, setRegisteredEmail] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [home, setHome] = useState<Awaited<ReturnType<typeof discoveryHome>> | null>(null);
  const [status, setStatus] = useState("Listo");
  const [transitioning, setTransitioning] = useState(false);
  const [section, setSection] = useState<"home" | "library">("home");
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [playlists, setPlaylists] = useState<Awaited<ReturnType<typeof listPlaylists>>>([]);
  const [newPlaylist, setNewPlaylist] = useState("");
  const [libraryBusy, setLibraryBusy] = useState(false);
  const [playlistMenuTrack, setPlaylistMenuTrack] = useState<string | null>(null);
  const [activeTrackId, setActiveTrackId] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchBusy, setSearchBusy] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("kubanfy:recent-searches") || "[]");
      return Array.isArray(saved) ? saved.filter((item): item is string => typeof item === "string").slice(0, 3) : [];
    } catch { return []; }
  });
  const searchInputRef = useRef<HTMLInputElement>(null);
  const player = useRef(new KbyPlayer()).current;

  useEffect(() => {
    player.onState = setStatus;
    void me().then(setUser).catch(() => {});
    return () => player.stop();
  }, [player]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setStatus("Cargando tu música…");
    void discoveryHome()
      .then(data => { if (!cancelled) { setHome(data); setStatus("Listo"); } })
      .catch(e => { if (!cancelled) setStatus(e instanceof Error ? e.message : "No pudimos cargar tu inicio."); });
    return () => { cancelled = true; };
  }, [user]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    void Promise.all([listFavorites(), listPlaylists()])
      .then(([fav, pls]) => {
        if (cancelled) return;
        setFavorites(new Set(fav.filter(item => item.target_type === "track").map(item => item.target_id)));
        setPlaylists(pls);
      })
      .catch(e => { if (!cancelled) setStatus(e instanceof Error ? e.message : "No pudimos cargar tu biblioteca."); });
    return () => { cancelled = true; };
  }, [user]);

  async function doLogin(email: string, password: string) {
    try {
      setStatus("Iniciando sesión…");
      const authenticatedUser = await login(email, password);
      setStatus("Conectado");
      setTransitioning(true);

      // Keep the loading state visible long enough for the login surface
      // to dissolve before mounting the Dashboard.
      await new Promise(resolve => window.setTimeout(resolve, 650));
      setUser(authenticatedUser);
      setTransitioning(false);
    } catch (e) {
      setTransitioning(false);
      const message = e instanceof Error ? e.message : "No pudimos iniciar sesión.";
      setStatus(message);
      throw e;
    }
  }

  async function toggleFavorite(trackId: string) {
    const wasFavorite = favorites.has(trackId);
    setFavorites(prev => {
      const next = new Set(prev);
      wasFavorite ? next.delete(trackId) : next.add(trackId);
      return next;
    });
    try {
      if (wasFavorite) await removeFavorite(trackId);
      else await addFavorite(trackId);
    } catch (e) {
      setFavorites(prev => {
        const next = new Set(prev);
        wasFavorite ? next.add(trackId) : next.delete(trackId);
        return next;
      });
      setStatus(e instanceof Error ? e.message : "No pudimos actualizar favoritos.");
    }
  }

  async function makePlaylist() {
    const name = newPlaylist.trim();
    if (!name || libraryBusy) return;
    setLibraryBusy(true);
    try {
      const created = await createPlaylist(name);
      setPlaylists(prev => [created, ...prev]);
      setNewPlaylist("");
      setStatus("Playlist creada");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No pudimos crear la playlist.");
    } finally {
      setLibraryBusy(false);
    }
  }

  async function removePlaylist(id: string) {
    if (libraryBusy) return;
    setLibraryBusy(true);
    try {
      await deletePlaylist(id);
      setPlaylists(prev => prev.filter(p => p.id !== id));
      setStatus("Playlist eliminada");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No pudimos eliminar la playlist.");
    } finally {
      setLibraryBusy(false);
    }
  }

  async function saveToPlaylist(playlistId: string, trackId: string) {
    try {
      await addTrackToPlaylist(playlistId, trackId);
      setPlaylistMenuTrack(null);
      setStatus("Añadida a la playlist");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No pudimos añadir la canción.");
    }
  }

  function rememberSearch(value: string) {
    const normalized = value.trim();
    if (!normalized) return;
    setRecentSearches(prev => {
      const next = [normalized, ...prev.filter(item => item.toLowerCase() !== normalized.toLowerCase())].slice(0, 3);
      try { localStorage.setItem("kubanfy:recent-searches", JSON.stringify(next)); } catch {}
      return next;
    });
  }

  async function search(value = query) {
    const normalized = value.trim();
    if (!normalized) { setResults([]); return; }
    try {
      setSearchBusy(true);
      const next = await searchTracks(normalized);
      setResults(next);
      rememberSearch(normalized);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No pudimos completar la búsqueda.");
    } finally { setSearchBusy(false); }
  }

  useEffect(() => {
    if (!searchOpen) return;
    const timer = window.setTimeout(() => searchInputRef.current?.focus(), 50);
    return () => window.clearTimeout(timer);
  }, [searchOpen]);

  useEffect(() => {
    if (!searchOpen) return;
    const normalized = query.trim();
    if (!normalized) { setResults([]); setSearchBusy(false); return; }
    const timer = window.setTimeout(() => void search(normalized), 300);
    return () => window.clearTimeout(timer);
  }, [query, searchOpen]);

  async function play(id: string) {
    try {
      setActiveTrackId(id);
      await player.load(id, "low");
    } catch (e) {
      setActiveTrackId(null);
      setStatus(e instanceof Error ? e.message : "Error de reproducción");
    }
  }

  function logout() {
    player.stop();
    setActiveTrackId(null);
    clearTokens();
    location.reload();
  }

  if (!user) {
    if (authMode === "register") {
      return (
        <div className="view-transition login-view">
          <RegisterView
            onBack={() => setAuthMode("login")}
            onRegistered={email => {
              setRegisteredEmail(email);
              setStatus("Cuenta creada. Ya puedes iniciar sesión.");
              setAuthMode("login");
            }}
          />
        </div>
      );
    }

    return (
      <div className={`view-transition login-view${transitioning ? " view-exit" : ""}`}>
        <LoginView onLogin={doLogin} onRegister={() => setAuthMode("register")} initialEmail={registeredEmail} />
      </div>
    );
  }

  return <div className="view-transition dashboard-view"><main className="app-page">
    <header className="topbar glass">
      <div className="brand-lockup"><LogoMark /><strong>KubanFy</strong></div>
      <div className="topbar-actions">
        <div className="status-pill"><span className="status-dot" />{status}</div>
        <button className="logout-button" onClick={logout}>Salir</button>
      </div>
    </header>

    <section className="content">
    <nav className="app-nav glass" aria-label="Navegación principal">
      <button className={section === "home" ? "active" : ""} aria-current={section === "home" ? "page" : undefined} onClick={() => setSection("home")}><span>⌂</span>Inicio</button>
      <button className={section === "library" ? "active" : ""} aria-current={section === "library" ? "page" : undefined} onClick={() => setSection("library")}><LibraryIcon />Biblioteca</button>
    </nav>

      {section === "home" && <div className="home-content">
      <div className="hero glass">
        <div>
          <span className="eyebrow">KUBANFY · {home?.country ?? "CUBA"}</span>
          <h1>Tu música, <em>a tu manera.</em></h1>
          <p>Descubre lo que está sonando y encuentra algo nuevo para escuchar.</p>
        </div>
      </div>

      <button className="glass search-panel search-launcher" onClick={() => setSearchOpen(true)} aria-label="Abrir búsqueda">
        <div className="search-row"><div className="search-input"><SearchIcon /><span>{query || "Artista, canción o álbum"}</span></div></div>
      </button>

      {results.length > 0 && (
        <section className="discovery-section">
          <div className="section-heading"><div><span className="eyebrow">RESULTADOS</span><h2>Encontrado para ti</h2></div></div>
          <div className="results">
            {results.map(r => <article className="glass track" key={r.provider_track_id}>
              <div className="track-art">{r.artwork ? <img src={r.artwork} alt="" /> : <LogoMark />}</div>
              <div className="track-info"><strong>{r.title}</strong><span>{r.artists.join(", ")}</span></div>
              {r.track_id && (
                <>
                  <div className="track-actions">
                    <button className={`icon-button favorite-button${favorites.has(r.track_id) ? " is-active" : ""}`} onClick={() => void toggleFavorite(r.track_id)} aria-label={favorites.has(r.track_id) ? "Quitar de favoritos" : "Añadir a favoritos"}><HeartIcon filled={favorites.has(r.track_id)} /></button>
                    <button className="icon-button" onClick={() => setPlaylistMenuTrack(playlistMenuTrack === r.track_id ? null : r.track_id)} aria-label="Añadir a playlist"><PlusIcon /></button>
                    <button className="play-button" onClick={() => void play(r.track_id)} aria-label={`Reproducir ${r.title}`}>▶</button>
                  </div>
                  {playlistMenuTrack === r.track_id && <div className="playlist-popover glass">
                    {playlists.length === 0 ? <span>Crea una playlist en Biblioteca.</span> : playlists.map(pl => <button key={pl.id} onClick={() => void saveToPlaylist(pl.id, r.track_id)}>{pl.name}</button>)}
                  </div>}
                </>
              )}
            </article>)}
          </div>
        </section>
      )}

      {home && (
        <>
          <section className="discovery-section">
            <div className="section-heading">
              <div><span className="eyebrow">PARA EMPEZAR</span><h2>Tendencias</h2></div>
            </div>
            <div className="featured-grid">
              {home.trending.slice(0, 5).map((track, index) => (
                <article className="featured-track glass" key={track.track_id}>
                  <span className="featured-number">{String(index + 1).padStart(2, "0")}</span>
                  <button className="featured-main" onClick={() => void play(track.track_id)} aria-label={`Reproducir ${track.title || "Sin título"}`}>
                    <span className="featured-title">{track.title || "Sin título"}</span>
                  </button>
                  <div className="featured-actions">
                    <button className={`featured-action${favorites.has(track.track_id) ? " is-active" : ""}`} onClick={() => void toggleFavorite(track.track_id)} aria-label={favorites.has(track.track_id) ? "Quitar de favoritos" : "Añadir a favoritos"}><HeartIcon filled={favorites.has(track.track_id)} /></button>
                    <button className="featured-action featured-play" onClick={() => void play(track.track_id)} aria-label={`Reproducir ${track.title || "Sin título"}`}>▶</button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="discovery-section">
            <div className="section-heading">
              <div><span className="eyebrow">RECIÉN LLEGADO</span><h2>Nuevos lanzamientos</h2></div>
            </div>
            <div className="release-row">
              {home.new_releases.slice(0, 8).map(track => (
                <article className="release-card glass" key={track.id}>
                  <button className="release-main" onClick={() => void play(track.id)} aria-label={`Reproducir ${track.title}`}>
                    <span className="release-art"><LogoMark /></span>
                    <strong>{track.title}</strong>
                    <span>{formatDuration(track.duration)}</span>
                  </button>
                  <div className="release-actions">
                    <button className={`release-action${favorites.has(track.id) ? " is-active" : ""}`} onClick={() => void toggleFavorite(track.id)} aria-label={favorites.has(track.id) ? "Quitar de favoritos" : "Añadir a favoritos"}><HeartIcon filled={favorites.has(track.id)} /></button>
                    <button className="release-action" onClick={() => void play(track.id)} aria-label={`Reproducir ${track.title}`}>▶</button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="discovery-section">
            <div className="section-heading">
              <div><span className="eyebrow">ESCENA LOCAL</span><h2>Artistas de {home.country}</h2></div>
            </div>
            <div className="artist-row">
              {home.local_artists.slice(0, 10).map(artist => (
                <div className="artist-card glass" key={artist.id}>
                  <span className="artist-avatar"><LogoMark /></span>
                  <strong>{artist.name}</strong>
                  {artist.verified && <span>Verificado</span>}
                </div>
              ))}
            </div>
          </section>
        </>
      )}
      </div>}

      {section === "library" && (
        <section className="library-page">
          <div className="library-header glass">
            <div><span className="eyebrow">TU COLECCIÓN</span><h1>Biblioteca</h1><p>Tus canciones y playlists, sincronizadas con tu cuenta.</p></div>
          </div>

          <section className="library-section">
            <div className="section-heading"><div><span className="eyebrow">GUARDADOS</span><h2>Favoritos</h2></div></div>
            {favorites.size === 0 ? (
              <div className="empty-state glass"><strong>Aún no tienes favoritos</strong><span>Guarda una canción con ♡ y aparecerá aquí.</span></div>
            ) : (
              <div className="library-list">
                {Array.from(favorites).map(id => {
                  const track = [...results, ...(home?.trending ?? []), ...(home?.new_releases ?? [])].find((item: any) => (item.track_id ?? item.id) === id);
                  return <article className="glass library-track" key={id}>
                    <div className="track-art"><LogoMark /></div>
                    <div className="track-info"><strong>{track?.title || "Canción guardada"}</strong><span>{track ? "KubanFy" : "Disponible en tu biblioteca"}</span></div>
                    <button className="play-button" onClick={() => void play(id)} aria-label="Reproducir favorito">▶</button>
                    <button className="icon-button favorite-button is-active" onClick={() => void toggleFavorite(id)} aria-label="Quitar de favoritos"><HeartIcon filled /></button>
                  </article>;
                })}
              </div>
            )}
          </section>

          <section className="library-section">
            <div className="section-heading"><div><span className="eyebrow">ORGANIZA</span><h2>Playlists</h2></div></div>
            <div className="playlist-create glass">
              <input value={newPlaylist} onChange={e => setNewPlaylist(e.target.value)} onKeyDown={e => e.key === "Enter" && void makePlaylist()} placeholder="Nombre de la nueva playlist" maxLength={200} />
              <button className="primary-button" onClick={() => void makePlaylist()} disabled={libraryBusy || !newPlaylist.trim()}>Crear</button>
            </div>
            {playlists.length === 0 ? (
              <div className="empty-state glass"><strong>Crea tu primera playlist</strong><span>Organiza tus canciones sin depender de la conexión.</span></div>
            ) : (
              <div className="playlist-grid">
                {playlists.map(pl => <article className="glass playlist-card" key={pl.id}>
                  <div className="playlist-cover"><LogoMark /></div>
                  <div className="playlist-meta"><strong>{pl.name}</strong><span>{pl.visibility === "private" ? "Privada" : "Pública"}</span></div>
                  <button className="icon-button" onClick={() => void removePlaylist(pl.id)} aria-label={`Eliminar ${pl.name}`}>×</button>
                </article>)}
              </div>
            )}
          </section>
        </section>
      )}

      {searchOpen && (
        <div className="search-overlay" role="dialog" aria-modal="true" aria-label="Buscar música" onMouseDown={e => { if (e.target === e.currentTarget) setSearchOpen(false); }}>
          <div className="search-dialog glass">
            <div className="search-dialog-head">
              <button className="icon-button search-close" onClick={() => setSearchOpen(false)} aria-label="Cerrar búsqueda">×</button>
              <strong>Buscar música</strong><span />
            </div>
            <div className="search-dialog-input search-input">
              <SearchIcon />
              <input ref={searchInputRef} value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === "Escape") setSearchOpen(false); }} placeholder="Artista, canción o álbum" aria-label="Buscar música" autoComplete="off" />
              {query && <button className="search-clear" onClick={() => setQuery("")} aria-label="Borrar búsqueda">×</button>}
              {searchBusy && <span className="search-spinner" aria-label="Buscando" />}
            </div>
            {!query.trim() && recentSearches.length > 0 && (
              <section className="search-history">
                <div className="search-dialog-label"><span>ÚLTIMAS BÚSQUEDAS</span><button onClick={() => { setRecentSearches([]); try { localStorage.removeItem("kubanfy:recent-searches"); } catch {} }}>Borrar</button></div>
                {recentSearches.map(item => <button className="search-history-item" key={item} onClick={() => setQuery(item)}><span className="history-icon">↺</span><span>{item}</span></button>)}
              </section>
            )}
            {query.trim() && (
              <section className="search-live-results">
                {searchBusy && results.length === 0 && <div className="search-empty">Buscando…</div>}
                {!searchBusy && results.length === 0 && <div className="search-empty">No encontramos resultados para «{query.trim()}».</div>}
                {results.map(r => r.track_id ? (
                  <article className="search-result-item" key={r.provider_track_id}>
                    <button className="search-result-main" onClick={() => { void play(r.track_id!); setSearchOpen(false); }}>
                      <span className="search-result-art">{r.artwork ? <img src={r.artwork} alt="" /> : <LogoMark />}</span>
                      <span><strong>{r.title}</strong><small>{r.artists.join(", ")}</small></span>
                    </button>
                    <button className={`icon-button favorite-button${favorites.has(r.track_id) ? " is-active" : ""}`} onClick={() => void toggleFavorite(r.track_id!)} aria-label={favorites.has(r.track_id) ? "Quitar de favoritos" : "Añadir a favoritos"}><HeartIcon filled={favorites.has(r.track_id)} /></button>
                  </article>
                ) : null)}
              </section>
            )}
          </div>
        </div>
      )}

      {activeTrackId && (
        <div className="player glass" aria-label="Reproductor">
          <div className="audio-host" ref={el => { if (el && !el.contains(player.element)) el.appendChild(player.element); }} />
          <button className="player-close" onClick={() => { player.stop(); setActiveTrackId(null); }} aria-label="Cerrar reproductor">×</button>
        </div>
      )}
    </section>
  </main></div>;
}
