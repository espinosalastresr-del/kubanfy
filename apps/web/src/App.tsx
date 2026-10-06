import { FormEvent, useEffect, useRef, useState } from "react";
import { clearTokens, login, me, register, searchTracks } from "./api";
import { KbyPlayer } from "./player";

function EyeIcon({ hidden }: { hidden: boolean }) {
  return hidden ? (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.7a2 2 0 0 0 2.7 2.7M9.9 5.2A10.8 10.8 0 0 1 12 5c5 0 8.5 4.1 9.5 6a17.7 17.7 0 0 1-3.1 3.7M6.2 6.2C3.9 7.7 2.5 10 2.5 12c1 1.9 4.5 6 9.5 6 1.7 0 3.2-.4 4.5-1.1" /></svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12S6 6 12 6s9.5 6 9.5 6S18 18 12 18s-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.8" /></svg>
  );
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
  
  useEffect(() => {
    setEmail(initialEmail);
  }, [initialEmail]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    if (!email || !password || !email.includes("@")) return;
    setBusy(true);
    try { await onLogin(email.trim(), password); } catch { /* status is rendered by the form */ } finally { setBusy(false); }
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
            <a href="#recuperar" onClick={e => { e.preventDefault(); alert("La recuperación de contraseña estará disponible próximamente."); }}>¿Olvidaste tu contraseña?</a>
          </div>

          {notice && <div className="form-notice" role="status">{notice}</div>}
          {status !== "Listo" && status !== "Conectado" && status !== "Iniciando sesión…" && (
            <div className="form-status" role="alert">{status}</div>
          )}

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

export default function App() {
  const [user, setUser] = useState<unknown>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [registeredEmail, setRegisteredEmail] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [status, setStatus] = useState("Listo");
  const [transitioning, setTransitioning] = useState(false);
  const player = useRef(new KbyPlayer()).current;

  useEffect(() => {
    player.onState = setStatus;
    void me().then(setUser).catch(() => {});
    return () => player.stop();
  }, [player]);

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
      setStatus(e instanceof Error ? e.message : "No pudimos iniciar sesión.");
      throw e;
    }
  }

  async function search() {
    try { setStatus("Buscando…"); setResults(await searchTracks(query)); setStatus("Listo"); }
    catch (e) { setStatus(e instanceof Error ? e.message : "Error de búsqueda"); }
  }

  async function play(id: string) {
    try { await player.load(id, "low"); }
    catch (e) { setStatus(e instanceof Error ? e.message : "Error de reproducción"); }
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
      <div className="status-pill"><span className="status-dot" />{status}</div>
    </header>

    <section className="content">
      <div className="hero glass">
        <div>
          <span className="eyebrow">DESCUBRE</span>
          <h1>Encuentra tu próxima canción.</h1>
          <p>Música pensada para tu conexión.</p>
        </div>
      </div>

      <div className="glass search-panel">
        <div className="search-row">
          <div className="search-input">
            <SearchIcon />
            <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && void search()} placeholder="Artista, canción o álbum" aria-label="Buscar música" />
          </div>
          <button className="primary-button search-button" onClick={() => void search()}>Buscar</button>
        </div>
      </div>

      {results.length > 0 && <div className="results">
        {results.map((r) => <article className="glass track" key={r.provider_track_id}>
          <div className="track-art">{r.artwork ? <img src={r.artwork} alt="" /> : <LogoMark />}</div>
          <div className="track-info"><strong>{r.title}</strong><span>{r.artists.join(", ")}</span></div>
          {r.track_id && <button className="play-button" onClick={() => void play(r.track_id)} aria-label={`Reproducir ${r.title}`}>▶</button>}
        </article>)}
      </div>}

      <div className="player glass"><div className="audio-host" ref={el => { if (el && !el.contains(player.element)) el.appendChild(player.element); }} /><button className="secondary-button" onClick={() => { clearTokens(); location.reload(); }}>Salir</button></div>
    </section>
  </main></div>;
}
