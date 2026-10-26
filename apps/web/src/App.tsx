import { FormEvent, useEffect, useRef, useState } from "react";
import { AdminAuditLog, AdminFeatureFlag, AdminUser, ApiError, ArtistManagedTrack, ArtistProfile, CurrentUser, ModerationReport, addFavorite, addTrackToPlaylist, getPlaylistTracks, getTrack, renamePlaylist, removeTrackFromPlaylist, clearTokens, confirmPasswordReset, createArtist, createPlaylist, deletePlaylist, discoveryHome, canManageUserPlans, createOfflineDownload, offlineLicensePublicKey, getDeviceId, listAdminAuditLogs, listAdminFeatureFlags, listAdminUsers, listArtistTracks, listModerationReports, listMyArtists, listFavorites, listPlaylists, listMyEntitlements, login, me, publishArtistTrack, register, removeFavorite, requestPasswordReset, resolveModerationReport, searchTracks, suspendAdminUser, unsuspendAdminUser, updateAdminFeatureFlag, updateAdminUserPlan, updateArtist, updateMyProfile, uploadArtistTrack } from "./api";
import { KbyPlayer } from "./player";
import { deleteOfflineTrack as deleteSavedOfflineTrack, downloadProtectedAudio, getPartialDownload, listOfflineTracks, saveOfflineTrack, verifyOfflineLicense, type OfflineTrack } from "./offline";

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

function LoginView({ onLogin, onRegister, onForgot, initialEmail }: { onLogin: (email: string, password: string) => Promise<void>; onRegister: () => void; onForgot: () => void; initialEmail: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
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
            <a href="#recuperar" onClick={e => { e.preventDefault(); onForgot(); }}>¿Olvidaste tu contraseña?</a>
          </div>

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

function PasswordRecoveryView({ onBack, initialEmail }: { onBack: () => void; initialEmail: string }) {
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = await requestPasswordReset(email.trim());
      setSent(true);
      setError(result.message);
    } catch {
      setError("No pudimos procesar la solicitud. Comprueba la conexión e inténtalo de nuevo.");
    } finally { setBusy(false); }
  }
  return <main className="auth-page"><div className="ambient ambient-one" /><div className="ambient ambient-two" />
    <section className="auth-shell"><div className="auth-brand"><LogoMark /><span>KubanFy</span></div>
      <div className="glass auth-card"><div className="auth-heading"><span className="eyebrow">RECUPERA TU CUENTA</span><h1>Volvamos a <em>sonar.</em></h1><p>Te enviaremos instrucciones si existe una cuenta asociada a ese correo.</p></div>
        <form onSubmit={submit}><label className="field"><span>Correo electrónico</span><input type="email" inputMode="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="tu@email.com" required /></label>
          {error && <div className={sent ? "form-notice" : "form-status"} role="status">{error}</div>}
          <button className="primary-button login-button" type="submit" disabled={busy || sent}>{busy ? "Enviando…" : sent ? "Solicitud enviada" : "Enviar instrucciones"}<span className="button-arrow">→</span></button>
        </form><div className="auth-divider"><span>o</span></div><p className="signup-prompt"><a href="#login" onClick={e => { e.preventDefault(); onBack(); }}>← Volver a iniciar sesión</a></p>
      </div><p className="auth-footnote">Por seguridad, no indicamos si un correo está registrado.</p>
    </section>
  </main>;
}

function PasswordResetView({ token, onBack, onComplete }: { token: string; onBack: () => void; onComplete: () => void }) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError("");
    if (password.length < 8 || (/^[A-Za-z]+$/.test(password) || /^\d+$/.test(password)) || password !== confirmation) {
      setError("Usa al menos 8 caracteres e incluye letras y números o símbolos; ambas contraseñas deben coincidir."); return;
    }
    setBusy(true);
    try {
      await confirmPasswordReset(token, password);
      setComplete(true);
      window.history.replaceState({}, "", window.location.pathname);
    } catch (e) {
      setError(e instanceof Error ? e.message : "El enlace no es válido o ha caducado. Solicita uno nuevo.");
    } finally { setBusy(false); }
  }
  return <main className="auth-page"><div className="ambient ambient-one" /><div className="ambient ambient-two" />
    <section className="auth-shell"><div className="auth-brand"><LogoMark /><span>KubanFy</span></div>
      <div className="glass auth-card"><div className="auth-heading"><span className="eyebrow">NUEVA CONTRASEÑA</span><h1>Protege tu <em>cuenta.</em></h1><p>{complete ? "Tu contraseña se ha actualizado correctamente." : "Elige una contraseña nueva para volver a tu música."}</p></div>
        {!complete && <form onSubmit={submit}><label className="field"><span>Nueva contraseña</span><input type="password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} minLength={8} required /></label>
          <label className="field"><span>Repetir contraseña</span><input type="password" autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} minLength={8} required /></label>
          {error && <div className="form-status" role="alert">{error}</div>}
          <button className="primary-button login-button" type="submit" disabled={busy}>{busy ? "Actualizando…" : "Guardar contraseña"}<span className="button-arrow">→</span></button>
        </form>}
        {complete && <button className="primary-button login-button" onClick={onComplete}>Ir a iniciar sesión <span className="button-arrow">→</span></button>}
        {!complete && <p className="signup-prompt"><a href="#login" onClick={e => { e.preventDefault(); onBack(); }}>← Volver a iniciar sesión</a></p>}
      </div><p className="auth-footnote">El enlace es temporal y solo se puede utilizar una vez.</p>
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

function AdminUsersView() {
  const [tab, setTab] = useState<"users" | "moderation" | "flags" | "audit">("users");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [plans, setPlans] = useState<Record<string, AdminUser["plan_code"]>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [reports, setReports] = useState<ModerationReport[]>([]);
  const [reportFilter, setReportFilter] = useState("");
  const [reportNotes, setReportNotes] = useState<Record<string, string>>({});
  const [takedown, setTakedown] = useState<Record<string, boolean>>({});
  const [flags, setFlags] = useState<AdminFeatureFlag[]>([]);
  const [audit, setAudit] = useState<AdminAuditLog[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadUsers(term = search) {
    setLoading(true); setError("");
    try {
      const rows = await listAdminUsers(term, 100, 0);
      setUsers(rows); setPlans(Object.fromEntries(rows.map(row => [row.id, row.plan_code])));
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo cargar la lista de usuarios."); }
    finally { setLoading(false); }
  }
  async function loadReports(filter = reportFilter) {
    setLoading(true); setError("");
    try { setReports(await listModerationReports(filter)); }
    catch (e) { setError(e instanceof Error ? e.message : "No se pudieron cargar los reportes. Comprueba el permiso de moderación."); }
    finally { setLoading(false); }
  }
  async function loadFlags() {
    setLoading(true); setError("");
    try { setFlags(await listAdminFeatureFlags()); }
    catch (e) { setError(e instanceof Error ? e.message : "No se pudieron cargar las funciones."); }
    finally { setLoading(false); }
  }
  async function loadAudit() {
    setLoading(true); setError("");
    try { setAudit(await listAdminAuditLogs(100)); }
    catch (e) { setError(e instanceof Error ? e.message : "No se pudo cargar la auditoría."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void loadUsers(""); }, []);

  async function changeTab(next: typeof tab) {
    setTab(next); setNotice(""); setError("");
    if (next === "users") await loadUsers();
    else if (next === "moderation") await loadReports();
    else if (next === "flags") await loadFlags();
    else await loadAudit();
  }
  async function savePlan(target: AdminUser) {
    const reason = (reasons[target.id] || "").trim();
    if (reason.length < 3) { setError("Escribe un motivo para dejar constancia del cambio."); return; }
    setBusyId(target.id); setError(""); setNotice("");
    try {
      await updateAdminUserPlan(target.id, plans[target.id] || target.plan_code, reason);
      setNotice(`Plan actualizado para ${target.email}.`);
      setReasons(prev => ({ ...prev, [target.id]: "" })); await loadUsers();
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo actualizar el plan."); }
    finally { setBusyId(null); }
  }
  async function changeSuspension(target: AdminUser) {
    const isSuspended = target.status === "suspended";
    const reason = (reasons[target.id] || "").trim();
    if (!isSuspended && reason.length < 3) { setError("Escribe un motivo de al menos 3 caracteres para suspender la cuenta."); return; }
    if (!window.confirm(isSuspended ? `¿Reactivar la cuenta de ${target.email}?` : `¿Suspender ${target.email} y revocar sus sesiones activas?`)) return;
    setBusyId(target.id); setError(""); setNotice("");
    try {
      if (isSuspended) await unsuspendAdminUser(target.id);
      else await suspendAdminUser(target.id, reason);
      setNotice(isSuspended ? "Cuenta reactivada." : "Cuenta suspendida; las sesiones activas se revocaron.");
      setReasons(prev => ({ ...prev, [target.id]: "" })); await loadUsers();
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo cambiar el estado de la cuenta."); }
    finally { setBusyId(null); }
  }
  async function resolveReport(report: ModerationReport, status: ModerationReport["status"]) {
    const notes = (reportNotes[report.id] || "").trim();
    if (status !== "reviewing" && notes.length < 3) { setError("Añade una nota de resolución de al menos 3 caracteres."); return; }
    if (takedown[report.id] && !window.confirm("Se retirará la canción del catálogo. ¿Continuar?")) return;
    setBusyId(report.id); setError(""); setNotice("");
    try {
      await resolveModerationReport(report.id, status, notes, Boolean(takedown[report.id]));
      setNotice("Reporte actualizado."); await loadReports();
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo actualizar el reporte."); }
    finally { setBusyId(null); }
  }
  async function toggleFlag(flag: AdminFeatureFlag) {
    setBusyId(flag.key); setError(""); setNotice("");
    try {
      await updateAdminFeatureFlag(flag.key, !flag.enabled);
      setFlags(prev => prev.map(item => item.key === flag.key ? { ...item, enabled: !flag.enabled } : item));
      setNotice(`Función «${flag.key}» ${flag.enabled ? "desactivada" : "activada"}.`);
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo cambiar la función."); }
    finally { setBusyId(null); }
  }

  return <section className="library-page">
    <div className="library-header glass"><div><span className="eyebrow">CONTROL DE KUBANFY</span><h1>Administración</h1><p>Gestiona cuentas, revisa reportes, controla funciones y consulta el registro de auditoría. Cada acción se vuelve a autorizar en el servidor.</p></div></div>
    <div className="admin-tabs" role="tablist" aria-label="Secciones administrativas">
      {([["users","Cuentas"],["moderation","Moderación"],["flags","Funciones"],["audit","Auditoría"]] as const).map(([key,label]) =>
        <button key={key} role="tab" aria-selected={tab===key} className={tab===key ? "active" : ""} onClick={() => void changeTab(key)}>{label}</button>)}
    </div>
    {error && <div className="form-status" role="alert">{error}</div>}
    {notice && <div className="form-notice" role="status">{notice}</div>}
    {loading && <div className="empty-state glass"><strong>Cargando…</strong></div>}

    {tab === "users" && <>
      <section className="library-section">
        <div className="section-heading"><div><span className="eyebrow">CUENTAS</span><h2>Usuarios y planes</h2></div><span>{users.length} cargados · máximo 100 por búsqueda</span></div>
        <form className="playlist-create glass" onSubmit={event => { event.preventDefault(); void loadUsers(); }}>
          <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Buscar por nombre o correo" maxLength={160} aria-label="Buscar usuarios" />
          <button className="primary-button" type="submit" disabled={loading}>Buscar</button>
        </form>
        {!loading && users.length === 0 && <div className="empty-state glass"><strong>No hay usuarios para mostrar</strong><span>Prueba otra búsqueda.</span></div>}
        <div className="admin-user-list">{users.map(target => <article className="glass admin-user-card" key={target.id}>
          <div className="admin-user-summary"><div><strong>{target.display_name}</strong><span>{target.email}</span></div>
            <div className="admin-user-tags"><span className="plan-tag">{(plans[target.id] || target.plan_code).toUpperCase()}</span><span className={target.status==="suspended" ? "status-danger" : ""}>{target.status}</span><span>{target.email_verified ? "Correo verificado" : "Correo sin verificar"}</span></div>
          </div>
          <div className="admin-user-controls">
            <label className="field"><span>Plan</span><select value={plans[target.id] || target.plan_code} onChange={event => setPlans(prev => ({ ...prev, [target.id]: event.target.value as AdminUser["plan_code"] }))}><option value="free">Free</option><option value="premium">Premium</option><option value="family">Family</option><option value="student">Student</option></select></label>
            <label className="field"><span>Motivo (obligatorio para cambios)</span><input value={reasons[target.id] || ""} onChange={event => setReasons(prev => ({ ...prev, [target.id]: event.target.value }))} placeholder="Motivo del cambio o suspensión" maxLength={500} /></label>
            <div className="artist-form-actions">
              <button className="primary-button" disabled={busyId===target.id || (plans[target.id] || target.plan_code)===target.plan_code || (reasons[target.id] || "").trim().length<3} onClick={() => void savePlan(target)}>{busyId===target.id ? "Guardando…" : "Guardar plan"}</button>
              <button className={target.status==="suspended" ? "primary-button" : "secondary-button"} disabled={busyId===target.id} onClick={() => void changeSuspension(target)}>{target.status==="suspended" ? "Reactivar cuenta" : "Suspender cuenta"}</button>
            </div>
          </div>
        </article>)}</div>
      </section>
    </>}

    {tab === "moderation" && <section className="library-section">
      <div className="section-heading"><div><span className="eyebrow">SEGURIDAD DEL CATÁLOGO</span><h2>Reportes de contenido</h2></div><span>{reports.length} reportes</span></div>
      <div className="playlist-create glass"><label className="field"><span>Estado</span><select value={reportFilter} onChange={e=>{setReportFilter(e.target.value);void loadReports(e.target.value);}}><option value="">Todos</option><option value="open">Abiertos</option><option value="reviewing">En revisión</option><option value="resolved">Resueltos</option><option value="rejected">Rechazados</option></select></label><button className="secondary-button" onClick={()=>void loadReports()}>Actualizar</button></div>
      {!loading && reports.length===0 && <div className="empty-state glass"><strong>No hay reportes en este filtro</strong></div>}
      <div className="admin-user-list">{reports.map(report=><article className="glass admin-user-card" key={report.id}>
        <div className="admin-user-summary"><div><strong>{report.report_type.replaceAll("_"," ").toUpperCase()} · {report.target_type}</strong><span>ID objetivo: {report.target_id}</span><span>{new Date(report.created_at).toLocaleString()}</span></div><div className="admin-user-tags"><span className="plan-tag">{report.status}</span></div></div>
        <p>{report.description || "Sin descripción proporcionada."}</p>
        <label className="field"><span>Notas de moderación</span><textarea rows={2} maxLength={2000} value={reportNotes[report.id] || ""} onChange={e=>setReportNotes(prev=>({...prev,[report.id]:e.target.value}))} placeholder="Documenta la decisión" /></label>
        {report.target_type==="track" && <label className="artist-check"><input type="checkbox" checked={Boolean(takedown[report.id])} onChange={e=>setTakedown(prev=>({...prev,[report.id]:e.target.checked}))}/> Retirar la canción del catálogo al resolver</label>}
        <div className="artist-form-actions"><button className="secondary-button" disabled={busyId===report.id} onClick={()=>void resolveReport(report,"reviewing")}>Marcar en revisión</button><button className="primary-button" disabled={busyId===report.id} onClick={()=>void resolveReport(report,"resolved")}>Resolver</button><button className="secondary-button" disabled={busyId===report.id} onClick={()=>void resolveReport(report,"rejected")}>Rechazar</button></div>
      </article>)}</div>
    </section>}

    {tab === "flags" && <section className="library-section">
      <div className="section-heading"><div><span className="eyebrow">CONFIGURACIÓN OPERATIVA</span><h2>Funciones del sistema</h2></div><button className="secondary-button" onClick={()=>void loadFlags()}>Actualizar</button></div>
      <p className="artist-help">Cambiar una bandera no garantiza que un componente la aplique si no está conectado a esa configuración. Evita desactivar funciones críticas durante pruebas activas.</p>
      <div className="admin-user-list">{flags.map(flag=><article className="glass admin-user-card" key={flag.key}><div className="admin-user-summary"><div><strong>{flag.key.replaceAll("_"," ")}</strong><span>{flag.description || "Sin descripción"}</span></div><div className="admin-user-tags"><span className={flag.enabled ? "flag-enabled" : "plan-tag"}>{flag.enabled ? "ACTIVADA" : "DESACTIVADA"}</span></div></div><button className={flag.enabled ? "secondary-button" : "primary-button"} disabled={busyId===flag.key} onClick={()=>void toggleFlag(flag)}>{busyId===flag.key ? "Guardando…" : flag.enabled ? "Desactivar" : "Activar"}</button></article>)}</div>
    </section>}

    {tab === "audit" && <section className="library-section">
      <div className="section-heading"><div><span className="eyebrow">TRAZABILIDAD</span><h2>Registro de auditoría</h2></div><button className="secondary-button" onClick={()=>void loadAudit()}>Actualizar</button></div>
      <div className="admin-user-list">{audit.map(log=><article className="glass admin-user-card" key={log.id}><div className="admin-user-summary"><div><strong>{log.action}</strong><span>{log.target_type || "—"} · {log.target_id || "—"}</span><span>{new Date(log.created_at).toLocaleString()}</span></div><div className="admin-user-tags"><span className="plan-tag">{log.result}</span></div></div>{log.reason && <p>Motivo: {log.reason}</p>}<details><summary>Detalles del cambio</summary><pre className="audit-json">{JSON.stringify({before:log.before ?? null,after:log.after ?? null},null,2)}</pre></details></article>)}</div>
      {!loading && audit.length===0 && <div className="empty-state glass"><strong>No hay eventos de auditoría</strong></div>}
    </section>}
  </section>;
}

function ArtistPortalView() {
  const [artists, setArtists] = useState<ArtistProfile[]>([]);
  const [artistId, setArtistId] = useState("");
  const [tracks, setTracks] = useState<ArtistManagedTrack[]>([]);
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [country, setCountry] = useState("CU");
  const [newArtist, setNewArtist] = useState(false);
  const [trackTitle, setTrackTitle] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [acceptLicense, setAcceptLicense] = useState(false);
  const [explicit, setExplicit] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadArtists(preferredId = artistId) {
    setLoading(true); setError("");
    try {
      const rows = await listMyArtists();
      setArtists(rows);
      setNewArtist(rows.length === 0);
      const chosen = rows.find(item => item.id === preferredId) || rows[0];
      setArtistId(chosen?.id || "");
      if (chosen) {
        setName(chosen.name); setBio(chosen.bio || ""); setCountry(chosen.country || "CU");
        const ownedTracks = await listArtistTracks(chosen.id);
        setTracks(ownedTracks);
      } else setTracks([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar el portal de artistas.");
    } finally { setLoading(false); }
  }
  useEffect(() => { void loadArtists(""); }, []);

  async function saveArtist(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const saved = newArtist
        ? await createArtist(name.trim(), bio.trim(), country.toUpperCase())
        : await updateArtist(artistId, name.trim(), bio.trim(), country.toUpperCase());
      setNewArtist(false); setNotice("Perfil de artista guardado.");
      await loadArtists(saved.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el perfil.");
    } finally { setBusy(false); }
  }
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!artistId || !audioFile || !trackTitle.trim() || !acceptLicense) {
      setError("Selecciona un archivo, indica el título y acepta la declaración de derechos.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await uploadArtistTrack(artistId, trackTitle.trim(), audioFile, acceptLicense, explicit, "es");
      setNotice(`Audio recibido. Estado: ${result.status}. La preparación puede tardar unos minutos.`);
      setTrackTitle(""); setAudioFile(null); setAcceptLicense(false);
      const input = document.getElementById("artist-audio-file") as HTMLInputElement | null;
      if (input) input.value = "";
      setTracks(await listArtistTracks(artistId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo subir el audio.");
    } finally { setBusy(false); }
  }
  async function publish(track: ArtistManagedTrack) {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await publishArtistTrack(artistId, track.id);
      setNotice(`Estado actualizado: ${result.status}.`);
      setTracks(await listArtistTracks(artistId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo publicar la canción. Comprueba que el procesamiento haya terminado.");
    } finally { setBusy(false); }
  }

  return <section className="library-page">
    <div className="library-header glass"><div><span className="eyebrow">CREADORES KUBANFY</span><h1>Portal de artistas</h1><p>Administra tu perfil y entrega música al catálogo. El audio se valida y procesa antes de poder publicarse.</p></div></div>
    {error && <div className="form-status" role="alert">{error}</div>}
    {notice && <div className="form-notice" role="status">{notice}</div>}
    {loading ? <div className="empty-state glass"><strong>Cargando portal…</strong></div> : <>
      <section className="library-section">
        <div className="section-heading"><div><span className="eyebrow">IDENTIDAD</span><h2>Perfil de artista</h2></div></div>
        {artists.length > 1 && !newArtist && <label className="field"><span>Artista</span><select value={artistId} onChange={async e => { const id=e.target.value; setArtistId(id); const selected=artists.find(a=>a.id===id); if(selected){setName(selected.name);setBio(selected.bio||"");setCountry(selected.country||"CU");} try{setTracks(await listArtistTracks(id));}catch(err){setError(err instanceof Error?err.message:"No se pudieron cargar las canciones.");} }}><option value="">Selecciona un artista</option>{artists.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>}
        {artists.length === 0 && <div className="empty-state glass"><strong>Aún no tienes un perfil de artista</strong><span>Crea uno para poder enviar tus canciones a revisión y procesamiento.</span></div>}
        <form className="glass artist-form" onSubmit={saveArtist}>
          <label className="field"><span>Nombre artístico</span><input value={name} onChange={e=>setName(e.target.value)} required maxLength={255} placeholder="Nombre del artista" /></label>
          <label className="field"><span>Biografía</span><textarea value={bio} onChange={e=>setBio(e.target.value)} maxLength={4000} rows={3} placeholder="Cuenta brevemente tu historia musical" /></label>
          <label className="field"><span>País (código ISO de 2 letras)</span><input value={country} onChange={e=>setCountry(e.target.value.toUpperCase().slice(0,2))} required minLength={2} maxLength={2} /></label>
          <div className="artist-form-actions"><button className="primary-button" disabled={busy || (!newArtist && !artistId)}>{busy ? "Guardando…" : newArtist ? "Crear perfil" : "Guardar perfil"}</button>
          {artists.length > 0 && <button type="button" className="secondary-button" onClick={()=>{setNewArtist(v=>!v);setName("");setBio("");setCountry("CU");}}>{newArtist ? "Cancelar" : "Añadir otro artista"}</button>}</div>
        </form>
      </section>
      {artistId && !newArtist && <section className="library-section">
        <div className="section-heading"><div><span className="eyebrow">CATÁLOGO</span><h2>Subir canción</h2></div></div>
        <form className="glass artist-form" onSubmit={upload}>
          <label className="field"><span>Título de la canción</span><input value={trackTitle} onChange={e=>setTrackTitle(e.target.value)} required maxLength={255} placeholder="Título" /></label>
          <label className="field"><span>Archivo de audio</span><input id="artist-audio-file" type="file" accept=".mp3,.wav,.flac,.m4a,.aac,.ogg,.opus,.aiff,.aif" onChange={e=>setAudioFile(e.target.files?.[0] || null)} required /></label>
          <p className="artist-help">La subida consume datos{audioFile ? ` · Archivo seleccionado: ${(audioFile.size / (1024 * 1024)).toFixed(1)} MB` : ""}. Usa Wi‑Fi si el archivo es grande y no cierres la página hasta que termine. El límite depende de la configuración del servidor.</p>
          <label className="artist-check"><input type="checkbox" checked={explicit} onChange={e=>setExplicit(e.target.checked)} /> Contenido explícito</label>
          <label className="artist-check"><input type="checkbox" checked={acceptLicense} onChange={e=>setAcceptLicense(e.target.checked)} /> Confirmo que tengo los derechos necesarios y autorizo almacenamiento, procesamiento y distribución en KubanFy.</label>
          <button className="primary-button" disabled={busy || !audioFile || !acceptLicense || !trackTitle.trim()}>{busy ? "Subiendo / procesando…" : "Subir canción"}</button>
        </form>
      </section>}
      {artistId && !newArtist && <section className="library-section">
        <div className="section-heading"><div><span className="eyebrow">ESTADO DE PUBLICACIÓN</span><h2>Mis canciones</h2></div><span>{tracks.length} canciones</span></div>
        {tracks.length === 0 ? <div className="empty-state glass"><strong>Aún no hay canciones</strong><span>Cuando subas un audio, su estado aparecerá aquí.</span></div> : <div className="admin-user-list">{tracks.map(track=><article className="glass admin-user-card" key={track.id}><div className="admin-user-summary"><div><strong>{track.title}</strong><span>{track.release_title} · {formatDuration(track.duration)}</span></div><div className="admin-user-tags"><span className="plan-tag">{track.status.toUpperCase()}</span></div></div><div className="artist-form-actions">{track.status === "processing" || track.status === "draft" || track.status === "hidden" ? <button className="primary-button" disabled={busy} onClick={()=>void publish(track)}>Validar y publicar</button> : null}<button className="secondary-button" disabled={busy} onClick={()=>void loadArtists(artistId)}>Actualizar estado</button></div></article>)}</div>}
      </section>}
    </>}
  </section>;
}

function AccountView({onUpdated}:{onUpdated:(user:CurrentUser)=>void}) {
 const [profile,setProfile]=useState<CurrentUser|null>(null);
 const [entitlements,setEntitlements]=useState<Awaited<ReturnType<typeof listMyEntitlements>>>([]);
 const [displayName,setDisplayName]=useState(""),[country,setCountry]=useState("CU"),[language,setLanguage]=useState("es");
 const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState("");
 useEffect(()=>{let cancelled=false;void Promise.all([me(),listMyEntitlements()]).then(([u,e])=>{if(cancelled)return;setProfile(u);setDisplayName(u.display_name);setCountry(u.country||"CU");setLanguage(u.language||"es");setEntitlements(e)}).catch(e=>{if(!cancelled)setError(e instanceof Error?e.message:"No pudimos cargar tu cuenta.")});return()=>{cancelled=true}},[]);
 async function save(event:FormEvent){event.preventDefault();setBusy(true);setMessage("");setError("");try{const u=await updateMyProfile({display_name:displayName.trim(),country:country.trim().toUpperCase(),language:language.trim().toLowerCase()});setProfile(u);setDisplayName(u.display_name);onUpdated(u);setMessage("Tus datos se han actualizado.")}catch(e){setError(e instanceof Error?e.message:"No pudimos guardar los cambios.")}finally{setBusy(false)}}
 const active=entitlements.filter(e=>e.scope_type==="user_premium"&&e.status==="active"),ent=active.find(e=>e.source==="manual")||active[0],code=ent?.plan_code||(ent?"premium":"free");
 const plan=({free:"Free",premium:"Premium",family:"Family",student:"Student"} as Record<string,string>)[code]||"Free",features=ent?.features||{},expiry=ent?.expires_at?new Date(ent.expires_at):null;
 return <section className="account-page"><div className="library-header glass"><div><span className="eyebrow">TU CUENTA</span><h1>Perfil y plan</h1><p>Gestiona tus datos y consulta las prestaciones asignadas.</p></div></div>
 {error&&<div className="form-status" role="alert">{error}</div>}<div className="account-grid">
 <section className="glass account-card"><div className="section-heading"><div><span className="eyebrow">DATOS PERSONALES</span><h2>Perfil</h2></div></div>
 {profile?<form onSubmit={save}><label className="field"><span>Nombre visible</span><input value={displayName} onChange={e=>setDisplayName(e.target.value)} minLength={1} maxLength={120} required/></label>
 <label className="field"><span>Correo electrónico</span><input value={profile.email} readOnly aria-readonly="true"/><small>El correo no se puede cambiar desde esta pantalla.</small></label>
 <div className="account-form-row"><label className="field"><span>País (código ISO)</span><input value={country} onChange={e=>setCountry(e.target.value.toUpperCase())} minLength={2} maxLength={2} pattern="[A-Za-z]{2}" required/></label>
 <label className="field"><span>Idioma</span><select value={language} onChange={e=>setLanguage(e.target.value)}><option value="es">Español</option><option value="en">English</option></select></label></div>
 <div className="account-meta"><span>Estado: <strong>{profile.status}</strong></span><span>{profile.email_verified?"Correo verificado":"Correo pendiente de verificación"}</span></div>
 {message&&<div className="form-notice" role="status">{message}</div>}<button className="primary-button" type="submit" disabled={busy||!displayName.trim()||!/^[A-Za-z]{2}$/.test(country)}>{busy?"Guardando…":"Guardar cambios"}</button></form>:<p>{error?"No se pudo cargar el perfil.":"Cargando perfil…"}</p>}</section>
 <section className="glass account-card"><div className="section-heading"><div><span className="eyebrow">TU SUSCRIPCIÓN</span><h2>Plan {plan}</h2></div><span className={ent?"plan-tag plan-tag-premium":"plan-tag"}>{ent?"ACTIVO":"GRATUITO"}</span></div>
 <p className="account-plan-copy">{ent?"Este es el plan asignado actualmente a tu cuenta.":"Estás en el plan gratuito. Las mejoras de plan las gestiona manualmente el equipo de KubanFy."}</p>
 <ul className="account-feature-list"><li><span>✓</span>Reproducción en streaming</li><li><span>{features.quality_max&&features.quality_max!=="low"?"✓":"•"}</span>Calidad máxima: {features.quality_max||"low"}</li><li><span>{features.downloads?"✓":"—"}</span>{features.downloads?"Descargas sin conexión incluidas, sujetas a licencia":"Descargas persistentes no incluidas"}</li>{features.seats?<li><span>✓</span>Hasta {features.seats} miembros en el plan Family</li>:null}</ul>
 {expiry?<p className="account-meta">Acceso hasta: <strong>{expiry.toLocaleDateString()}</strong></p>:ent?<p className="account-meta">Vigencia: sin fecha de expiración registrada</p>:null}<p className="account-note">Los pagos automáticos están desactivados. Esta pantalla no realiza cobros.</p></section></div></section>;
}

function formatDuration(seconds: number | null | undefined) {
  if (!seconds || seconds < 0) return "—";
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

export default function App() {
  const [user, setUser] = useState<unknown>(null);
  const [authMode, setAuthMode] = useState<"login" | "register" | "forgot" | "reset">(() => new URLSearchParams(window.location.hash.slice(1)).has("reset_token") ? "reset" : "login");
  const [resetToken, setResetToken] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get("reset_token") || "");
  const [registeredEmail, setRegisteredEmail] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [home, setHome] = useState<Awaited<ReturnType<typeof discoveryHome>> | null>(null);
  const [status, setStatus] = useState("Listo");
  const [isOnline, setIsOnline] = useState(() => navigator.onLine);
  const [transitioning, setTransitioning] = useState(false);
  const [section, setSection] = useState<"home" | "library" | "admin" | "artist" | "account">("home");
  const [isAdmin, setIsAdmin] = useState(false);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [playlists, setPlaylists] = useState<Awaited<ReturnType<typeof listPlaylists>>>([]);
  const [newPlaylist, setNewPlaylist] = useState("");
  const [newPlaylistVisibility, setNewPlaylistVisibility] = useState<"private" | "public">("private");
  const [editingPlaylistVisibility, setEditingPlaylistVisibility] = useState<"private" | "public">("private");
  const [libraryBusy, setLibraryBusy] = useState(false);
  const [playlistMenuTrack, setPlaylistMenuTrack] = useState<string | null>(null);
  const [activeTrackId, setActiveTrackId] = useState<string | null>(null);
  const [activeTrack, setActiveTrack] = useState<{ id: string; title: string; artist: string; artwork?: string | null; duration?: number | null } | null>(null);
  const [queue, setQueue] = useState<Array<{ id: string; title: string; artist: string; artwork?: string | null; duration?: number | null }>>([]);
  const [queueIndex, setQueueIndex] = useState(0);
  const [playerTime, setPlayerTime] = useState(0);
  const [playerDuration, setPlayerDuration] = useState(0);
  const [playerPaused, setPlayerPaused] = useState(true);
  const [openedPlaylist, setOpenedPlaylist] = useState<string | null>(null);
  const [playlistTracks, setPlaylistTracks] = useState<Array<{ id: string; title: string; artist: string; artwork?: string | null; duration?: number | null }>>([]);
  const [editingPlaylist, setEditingPlaylist] = useState<string | null>(null);
  const [editingPlaylistName, setEditingPlaylistName] = useState("");
  const handledDeepLink = useRef("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchError, setSearchError] = useState("");
  const searchRequestId = useRef(0);
  const [recentSearches, setRecentSearches] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("kubanfy:recent-searches") || "[]");
      return Array.isArray(saved) ? saved.filter((item): item is string => typeof item === "string").slice(0, 3) : [];
    } catch { return []; }
  });
  const searchInputRef = useRef<HTMLInputElement>(null);
  const player = useRef(new KbyPlayer()).current;
  const [offlineTracks, setOfflineTracks] = useState<OfflineTrack[]>([]);
  const [downloadBusy, setDownloadBusy] = useState<string | null>(null);
  const [canDownload, setCanDownload] = useState(false);

  useEffect(() => {
    const update = () => { setPlayerTime(player.currentTime); setPlayerDuration(player.duration); setPlayerPaused(player.paused); };
    player.element.addEventListener("timeupdate", update);
    player.element.addEventListener("durationchange", update);
    player.element.addEventListener("play", update);
    player.element.addEventListener("pause", update);
    player.element.addEventListener("ended", update);
    const timer = window.setInterval(update, 1000);
    return () => { window.clearInterval(timer); player.element.removeEventListener("timeupdate", update); player.element.removeEventListener("durationchange", update); player.element.removeEventListener("play", update); player.element.removeEventListener("pause", update); player.element.removeEventListener("ended", update); };
  }, [player]);

  useEffect(() => { player.onNext = () => void moveQueue(1); player.onPrevious = () => void moveQueue(-1); }, [player, queue, queueIndex]);

  useEffect(() => {
    player.onState = setStatus;
    void me().then(setUser).catch(() => {});
    void listOfflineTracks().then(setOfflineTracks).catch(() => {});
    const markOnline = () => setIsOnline(true);
    const markOffline = () => setIsOnline(false);
    window.addEventListener("online", markOnline);
    window.addEventListener("offline", markOffline);
    return () => {
      window.removeEventListener("online", markOnline);
      window.removeEventListener("offline", markOffline);
      player.stop();
    };
  }, [player]);

  useEffect(() => {
    if (!user) {
      setIsAdmin(false);
      return;
    }
    let cancelled = false;
    void canManageUserPlans()
      .then(allowed => { if (!cancelled) setIsAdmin(allowed); })
      .catch(() => { if (!cancelled) setIsAdmin(false); });
    return () => { cancelled = true; };
  }, [user]);

  useEffect(() => {
    if (!user) { setCanDownload(false); return; }
    let cancelled = false;
    void listMyEntitlements().then(items => {
      if (!cancelled) setCanDownload(items.some(item =>
        item.scope_type === "user_premium" && item.status === "active" && item.features.downloads === true
      ));
    }).catch(() => { if (!cancelled) setCanDownload(false); });
    return () => { cancelled = true; };
  }, [user]);

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
      const created = await createPlaylist(name, newPlaylistVisibility);
      setPlaylists(prev => [created, ...prev]);
      setNewPlaylist("");
      setNewPlaylistVisibility("private");
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
    const requestId = ++searchRequestId.current;
    if (!normalized) {
      setResults([]);
      setSearchError("");
      setSearchBusy(false);
      return;
    }
    setSearchError("");
    setSearchBusy(true);
    try {
      const next = await searchTracks(normalized);
      if (requestId !== searchRequestId.current) return;
      setResults(next);
      rememberSearch(normalized);
    } catch (e) {
      if (requestId !== searchRequestId.current) return;
      setResults([]);
      setSearchError(!navigator.onLine
        ? "No hay conexión. Cuando vuelva la red, inténtalo de nuevo."
        : "No pudimos completar la búsqueda. Comprueba la conexión e inténtalo de nuevo.");
    } finally {
      if (requestId === searchRequestId.current) setSearchBusy(false);
    }
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

  async function play(id: string, title = "KubanFy", artist = "KubanFy", artwork?: string | null, nextQueue?: Array<{ id: string; title: string; artist: string; artwork?: string | null; duration?: number | null }>, index = 0) {
    try {
      if (title === "KubanFy") {
        try { const detail = await getTrack(id); title = detail.title; artist = detail.artists.map(item => item.name).join(", ") || "Artista desconocido"; artwork = detail.artwork_url; }
        catch { /* Playback authorization remains the source of truth if metadata lookup fails. */ }
      }
      const current = { id, title, artist, artwork };
      if (nextQueue) { setQueue(nextQueue); setQueueIndex(index); }
      else { setQueue([current]); setQueueIndex(0); }
      setActiveTrack(current);
      setActiveTrackId(id);
      await player.load(id, "low", title, artist, artwork);
      setPlayerPaused(player.paused);
    } catch (e) {
      setActiveTrackId(null);
      setActiveTrack(null);
      setStatus(e instanceof Error ? e.message : "Error de reproducción");
    }
  }

  async function moveQueue(offset: number) {
    if (!queue.length) return;
    const next = (queueIndex + offset + queue.length) % queue.length;
    const item = queue[next];
    await play(item.id, item.title, item.artist, item.artwork, queue, next);
  }

  useEffect(() => {
    if (!user) return;
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const playlistId = params.get("playlist");
    const trackId = params.get("track");
    const token = playlistId ? `playlist:${playlistId}` : trackId ? `track:${trackId}` : "";
    if (!token || handledDeepLink.current === token) return;
    handledDeepLink.current = token;
    if (playlistId) {
      setSection("library");
      void openPlaylist(playlistId);
    } else if (trackId) {
      void getTrack(trackId).then(track => {
        void play(track.id, track.title, track.artists.map(item => item.name).join(", ") || "Artista desconocido", track.artwork_url);
      }).catch(() => setStatus("No pudimos abrir esta canción. Puede que ya no esté disponible."));
    }
  }, [user, playlists]);

  async function shareLink(title: string, path: string) {
    const url = new URL(path, window.location.origin).toString();
    try {
      if (navigator.share) await navigator.share({ title, text: `Escucha ${title} en KubanFy`, url });
      else if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(url); setStatus("Enlace copiado para compartir."); }
      else { window.prompt("Copia este enlace para compartir:", url); }
    } catch (error) {
      if (error instanceof Error && error.name !== "AbortError") setStatus("No se pudo abrir el menú de compartir.");
    }
  }

  async function openPlaylist(id: string) {
    setOpenedPlaylist(id);
    try {
      const rows = await getPlaylistTracks(id);
      const details = await Promise.all(rows.map(async row => {
        try {
          const track = await getTrack(row.track_id);
          return { id: track.id, title: track.title, artist: track.artists.map(a => a.name).join(", ") || "Artista desconocido", artwork: track.artwork_url, duration: track.duration };
        } catch {
          return { id: row.track_id, title: "Canción no disponible", artist: "Puede que ya no esté publicada", artwork: null, duration: null };
        }
      }));
      setPlaylistTracks(details);
    } catch (e) {
      setPlaylistTracks([]);
      setStatus(e instanceof Error ? e.message : "No se pudo abrir la playlist.");
    }
  }

  async function savePlaylistName(id: string) {
    const name = editingPlaylistName.trim();
    if (!name) return;
    try {
      const updated = await renamePlaylist(id, name, editingPlaylistVisibility);
      setPlaylists(items => items.map(item => item.id === id ? updated : item));
      setEditingPlaylist(null);
      setStatus("Playlist actualizada.");
    } catch (e) { setStatus(e instanceof Error ? e.message : "No se pudo editar la playlist."); }
  }

  async function playPlaylist(index = 0) {
    const playable = playlistTracks.filter(track => track.title !== "Canción no disponible");
    if (!playable.length) { setStatus("Esta playlist no contiene canciones disponibles."); return; }
    const safeIndex = Math.max(0, Math.min(index, playable.length - 1));
    await play(playable[safeIndex].id, playable[safeIndex].title, playable[safeIndex].artist, playable[safeIndex].artwork, playable, safeIndex);
  }
  async function saveOffline(id: string, title: string) {
    if (downloadBusy) return;
    if (!isOnline) { setStatus("Necesitas conexión para iniciar la descarga."); return; }
    const currentUser = user as CurrentUser | null;
    if (!currentUser?.id) { setStatus("Inicia sesión para guardar música."); return; }
    if (offlineTracks.some(track => track.id === `${id}:low`)) {
      setStatus("Esta canción ya está guardada sin conexión.");
      return;
    }
    setDownloadBusy(id);
    try {
      setStatus("Preparando descarga segura…");
      const response = await createOfflineDownload(id, "low");
      if (!response.url || !response.offline_license || !response.content_hash || !response.kby_key ||
          response.asset_version == null || typeof response.size_bytes !== "number" ||
          response.size_bytes <= 0 || !response.offline_license_expires_at) {
        throw new Error("El servidor no entregó una descarga offline completa.");
      }
      const key = await offlineLicensePublicKey();
      if (key.algorithm !== "RS256" || !key.public_key) {
        throw new Error("La verificación de licencias offline no está configurada.");
      }
      const partial = await getPartialDownload(`partial:${id}:low`);
      if (navigator.storage?.estimate) {
        const estimate = await navigator.storage.estimate();
        if (typeof estimate.quota === "number" && typeof estimate.usage === "number" &&
            estimate.quota - estimate.usage < Math.max(0, response.size_bytes - (partial && partial.contentHash === response.content_hash && partial.assetVersion === response.asset_version && partial.deviceId === getDeviceId() && partial.totalBytes === response.size_bytes ? partial.receivedBytes : 0)) * 1.1) {
          throw new Error("No hay espacio suficiente en el dispositivo para guardar esta canción.");
        }
      }
      const blob = await downloadProtectedAudio(response.url, response.size_bytes, (received, total) => {
        setStatus(`${received > 0 && partial && partial.contentHash === response.content_hash && partial.assetVersion === response.asset_version && partial.deviceId === getDeviceId() && partial.totalBytes === response.size_bytes ? "Reanudando" : "Descargando"} ${title}: ${Math.floor(received / total * 100)}%`);
      }, { id: `partial:${id}:low`, trackId: id, quality: "low", contentHash: response.content_hash, assetVersion: response.asset_version, deviceId: getDeviceId() });
      const saved: OfflineTrack = {
        id: `${id}:low`, trackId: id, title, quality: "low", blob,
        kbyKey: response.kby_key, contentHash: response.content_hash,
        assetVersion: response.asset_version, licenseToken: response.offline_license,
        publicKey: key.public_key, expiresAt: response.offline_license_expires_at,
        deviceId: getDeviceId(), sizeBytes: blob.size, savedAt: Date.now(),
      };
      await verifyOfflineLicense(saved, currentUser.id);
      await saveOfflineTrack(saved);
      setOfflineTracks(await listOfflineTracks());
      setStatus("Canción guardada y verificada para modo offline.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudo guardar la canción sin conexión.");
    } finally {
      setDownloadBusy(null);
    }
  }

  async function playOffline(track: OfflineTrack) {
    const currentUser = user as CurrentUser | null;
    if (!currentUser?.id) { setStatus("Inicia sesión para validar la licencia offline."); return; }
    try {
      await verifyOfflineLicense(track, currentUser.id);
      setActiveTrackId(track.trackId);
      await player.loadOffline(track);
    } catch (e) {
      setActiveTrackId(null);
      setStatus(e instanceof Error ? e.message : "No se pudo reproducir la descarga offline.");
    }
  }

  async function removeOffline(track: OfflineTrack) {
    try {
      await deleteSavedOfflineTrack(track.id);
      setOfflineTracks(await listOfflineTracks());
      setStatus("Descarga eliminada del dispositivo.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "No se pudo eliminar la descarga.");
    }
  }


  function logout() {
    player.stop();
    setActiveTrackId(null);
    clearTokens();
    location.reload();
  }

  if (!user) {
    if (authMode === "reset" && resetToken) {
      return <div className="view-transition login-view"><PasswordResetView token={resetToken} onBack={() => { setAuthMode("login"); setResetToken(""); window.history.replaceState({}, "", window.location.pathname); }} onComplete={() => { setAuthMode("login"); setResetToken(""); }} /></div>;
    }
    if (authMode === "forgot") {
      return <div className="view-transition login-view"><PasswordRecoveryView initialEmail={registeredEmail} onBack={() => setAuthMode("login")} /></div>;
    }
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
        <LoginView onLogin={doLogin} onRegister={() => setAuthMode("register")} onForgot={() => setAuthMode("forgot")} initialEmail={registeredEmail} />
      </div>
    );
  }

  return <div className="view-transition dashboard-view"><main className="app-page">
    <header className="topbar glass">
      <div className="brand-lockup"><LogoMark /><strong>KubanFy</strong></div>
      <div className="topbar-actions">
        <div className={`status-pill${isOnline ? "" : " offline"}`} role="status" aria-live="polite">
          <span className="status-dot" />{isOnline ? status : "Sin conexión"}
        </div>
        <button className="logout-button" onClick={logout}>Salir</button>
      </div>
    </header>

    <section className="content">
    <nav className="app-nav glass" aria-label="Navegación principal">
      <button className={section === "home" ? "active" : ""} aria-current={section === "home" ? "page" : undefined} onClick={() => setSection("home")}><span>⌂</span>Inicio</button>
      <button className={section === "library" ? "active" : ""} aria-current={section === "library" ? "page" : undefined} onClick={() => setSection("library")}><LibraryIcon />Biblioteca</button>
      <button className={section === "account" ? "active" : ""} aria-current={section === "account" ? "page" : undefined} onClick={() => setSection("account")}><span>◉</span>Mi cuenta</button>
      <button className={section === "artist" ? "active" : ""} aria-current={section === "artist" ? "page" : undefined} onClick={() => setSection("artist")}><span>♫</span>Artistas</button>
      {isAdmin && <button className={section === "admin" ? "active" : ""} aria-current={section === "admin" ? "page" : undefined} onClick={() => setSection("admin")}><span>⚙</span>Administración</button>}
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
                    {!offlineTracks.some(saved => saved.id === `${r.track_id}:low`) && <button className="icon-button" disabled={!isOnline || downloadBusy !== null || !canDownload} onClick={() => void saveOffline(r.track_id, r.title)} aria-label={`Guardar ${r.title} sin conexión`} title={canDownload ? "Guardar sin conexión" : "Las descargas requieren un plan Premium, Family o Student"}>↓</button>}
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
                    {!offlineTracks.some(saved => saved.id === `${track.track_id}:low`) && <button className="featured-action" disabled={!isOnline || downloadBusy !== null || !canDownload} onClick={() => void saveOffline(track.track_id, track.title || "Sin título")} aria-label={`Guardar ${track.title || "canción"} sin conexión`} title={canDownload ? "Guardar sin conexión" : "Las descargas requieren un plan Premium, Family o Student"}>↓</button>}
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
                    {!offlineTracks.some(saved => saved.id === `${track.id}:low`) && <button className="release-action" disabled={!isOnline || downloadBusy !== null || !canDownload} onClick={() => void saveOffline(track.id, track.title)} aria-label={`Guardar ${track.title} sin conexión`} title={canDownload ? "Guardar sin conexión" : "Las descargas requieren un plan Premium, Family o Student"}>↓</button>}
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

      {section === "admin" && isAdmin && <AdminUsersView />}
      {section === "artist" && <ArtistPortalView />}
      {section === "account" && <AccountView onUpdated={updated => setUser(updated)} />}

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
            <div className="section-heading"><div><span className="eyebrow">DISPONIBLES SIN CONEXIÓN</span><h2>Descargas</h2></div><span className="plan-tag">{offlineTracks.length} guardadas</span></div>
            {offlineTracks.length === 0 ? (
              <div className="empty-state glass"><strong>Todavía no tienes descargas</strong><span>Guarda una canción con la flecha de descarga cuando tengas conexión. Las descargas quedan cifradas y vinculadas a tu dispositivo.</span></div>
            ) : (
              <div className="library-list">
                {offlineTracks.map(track => <article className="glass library-track" key={track.id}>
                  <div className="track-art"><LogoMark /></div>
                  <div className="track-info"><strong>{track.title}</strong><span>{track.quality.toUpperCase()} · {(track.sizeBytes / 1024 / 1024).toFixed(1)} MB · licencia hasta {new Date(track.expiresAt).toLocaleDateString()}</span></div>
                  <button className="play-button" onClick={() => void playOffline(track)} aria-label={`Reproducir ${track.title} sin conexión`}>▶</button>
                  <button className="icon-button" onClick={() => void removeOffline(track)} aria-label={`Eliminar ${track.title} descargada`}>×</button>
                </article>)}
              </div>
            )}
          </section>

          <section className="library-section">
            <div className="section-heading"><div><span className="eyebrow">ORGANIZA</span><h2>Playlists</h2></div></div>
            <div className="playlist-create glass">
              <input value={newPlaylist} onChange={e => setNewPlaylist(e.target.value)} onKeyDown={e => e.key === "Enter" && void makePlaylist()} placeholder="Nombre de la nueva playlist" maxLength={200} />
              <select value={newPlaylistVisibility} onChange={e => setNewPlaylistVisibility(e.target.value as "private" | "public")} aria-label="Visibilidad de la nueva playlist"><option value="private">Privada</option><option value="public">Pública</option></select>
              <button className="primary-button" onClick={() => void makePlaylist()} disabled={libraryBusy || !newPlaylist.trim()}>Crear</button>
            </div>
            {playlists.length === 0 ? (
              <div className="empty-state glass"><strong>Crea tu primera playlist</strong><span>Organiza tus canciones sin depender de la conexión.</span></div>
            ) : (
              <div className="playlist-grid">
                {playlists.map(pl => <article className="glass playlist-card" key={pl.id}>
                  <button className="playlist-open" onClick={() => void openPlaylist(pl.id)} aria-label={`Abrir playlist ${pl.name}`}><span className="playlist-cover"><LogoMark /></span><span className="playlist-meta"><strong>{pl.name}</strong><small>{pl.visibility === "private" ? "Privada" : "Pública"}</small></span></button>
                  <div className="playlist-card-actions">
                    <button className="icon-button" onClick={() => { setEditingPlaylist(pl.id); setEditingPlaylistName(pl.name); setEditingPlaylistVisibility(pl.visibility); }} aria-label={`Editar ${pl.name}`}>✎</button>
                    <button className="icon-button" onClick={() => void shareLink(pl.name, `/#playlist=${pl.id}`)} aria-label={`Compartir ${pl.name}`}>↗</button>
                    <button className="icon-button" onClick={() => void removePlaylist(pl.id)} aria-label={`Eliminar ${pl.name}`}>×</button>
                  </div>
                  {editingPlaylist === pl.id && <form className="playlist-edit" onSubmit={event => { event.preventDefault(); void savePlaylistName(pl.id); }}><input value={editingPlaylistName} onChange={event => setEditingPlaylistName(event.target.value)} maxLength={200} aria-label="Nombre de la playlist" /><select value={editingPlaylistVisibility} onChange={event => setEditingPlaylistVisibility(event.target.value as "private" | "public")} aria-label="Visibilidad de la playlist"><option value="private">Privada</option><option value="public">Pública · se puede compartir</option></select><button className="primary-button" type="submit">Guardar</button><button className="secondary-button" type="button" onClick={() => setEditingPlaylist(null)}>Cancelar</button></form>}
                </article>)}
              </div>
            )}
          </section>
          {openedPlaylist && <section className="library-section playlist-detail">
            <div className="section-heading"><div><span className="eyebrow">TU COLECCIÓN</span><h2>{playlists.find(pl => pl.id === openedPlaylist)?.name || "Playlist"}</h2><p>{playlistTracks.length} canciones</p></div>
              <div className="playlist-detail-actions"><button className="primary-button" onClick={() => void playPlaylist(0)} disabled={!playlistTracks.length}>▶ Reproducir todo</button><button className="secondary-button" onClick={() => void shareLink(playlists.find(pl => pl.id === openedPlaylist)?.name || "Playlist KubanFy", `/#playlist=${openedPlaylist}`)}>Compartir</button><button className="secondary-button" onClick={() => setOpenedPlaylist(null)}>Cerrar</button></div>
            </div>
            {playlistTracks.length === 0 ? <div className="empty-state glass">Cargando canciones…</div> : <div className="library-list">{playlistTracks.map((track,index) => <article className="glass library-track" key={track.id}>
              <div className="track-art">{track.artwork ? <img src={track.artwork} alt="" /> : <LogoMark />}</div><div className="track-info"><strong>{track.title}</strong><span>{track.artist}{track.duration ? ` · ${formatDuration(track.duration)}` : ""}</span></div>
              <button className="play-button" onClick={() => { const playable = playlistTracks.filter(item => item.title !== "Canción no disponible"); const queueIndex = playable.findIndex(item => item.id === track.id); if (queueIndex >= 0) void play(track.id, track.title, track.artist, track.artwork, playable, queueIndex); }} aria-label={`Reproducir ${track.title}`}>▶</button>
              <button className="icon-button" onClick={async () => { try { await removeTrackFromPlaylist(openedPlaylist, track.id); setPlaylistTracks(items => items.filter(item => item.id !== track.id)); setStatus("Canción eliminada de la playlist."); } catch (e) { setStatus(e instanceof Error ? e.message : "No se pudo eliminar la canción."); } }} aria-label={`Quitar ${track.title} de la playlist`}>×</button>
            </article>)}</div>}
          </section>}
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
              <input ref={searchInputRef} value={query} onChange={e => { searchRequestId.current += 1; setResults([]); setSearchError(""); setQuery(e.target.value); }} onKeyDown={e => { if (e.key === "Escape") setSearchOpen(false); }} placeholder="Artista, canción o álbum" aria-label="Buscar música" autoComplete="off" />
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
                {!searchBusy && searchError && <div className="search-empty" role="status">{searchError}<div><button className="search-retry" onClick={() => void search(query)}>Reintentar</button></div></div>}
                {!searchBusy && !searchError && results.length === 0 && <div className="search-empty">No encontramos resultados para «{query.trim()}».</div>}
                {results.map(r => r.track_id ? (
                  <article className="search-result-item" key={r.provider_track_id}>
                    <button className="search-result-main" onClick={() => { void play(r.track_id!); setSearchOpen(false); }}>
                      <span className="search-result-art">{r.artwork ? <img src={r.artwork} alt="" /> : <LogoMark />}</span>
                      <span><strong>{r.title}</strong><small>{r.artists.join(", ")}</small></span>
                    </button>
                    <button className={`icon-button favorite-button${favorites.has(r.track_id) ? " is-active" : ""}`} onClick={() => void toggleFavorite(r.track_id!)} aria-label={favorites.has(r.track_id) ? "Quitar de favoritos" : "Añadir a favoritos"}><HeartIcon filled={favorites.has(r.track_id)} /></button>
                    {!offlineTracks.some(saved => saved.id === `${r.track_id}:low`) && <button className="icon-button" disabled={!isOnline || downloadBusy !== null || !canDownload} onClick={() => void saveOffline(r.track_id!, r.title)} aria-label={`Guardar ${r.title} sin conexión`} title={canDownload ? "Guardar sin conexión" : "Las descargas requieren un plan Premium, Family o Student"}>↓</button>}
                  </article>
                ) : null)}
              </section>
            )}
          </div>
        </div>
      )}

      {activeTrackId && activeTrack && (
        <div className="player glass" aria-label="Reproductor">
          <div className="audio-host" ref={el => { if (el && !el.contains(player.element)) el.appendChild(player.element); }} />
          <div className="player-track"><div className="player-art">{activeTrack.artwork ? <img src={activeTrack.artwork} alt="" /> : <LogoMark />}</div><div className="player-track-meta"><strong>{activeTrack.title}</strong><span>{activeTrack.artist}</span></div></div>
          <div className="player-main-controls"><div className="player-buttons">
            <button className="player-control" onClick={() => void moveQueue(-1)} aria-label="Canción anterior">|◀</button>
            <button className="player-control player-toggle" onClick={() => { void player.playPause().then(() => setPlayerPaused(player.paused)).catch(() => setStatus("Pulsa reproducir para continuar.")); }} aria-label={playerPaused ? "Reproducir" : "Pausar"}>{playerPaused ? "▶" : "Ⅱ"}</button>
            <button className="player-control" onClick={() => void moveQueue(1)} aria-label="Siguiente canción">▶|</button>
          </div><div className="player-progress"><span>{formatDuration(playerTime)}</span><input type="range" min="0" max={Math.max(1,playerDuration)} step="1" value={Math.min(playerTime,Math.max(1,playerDuration))} onChange={event => player.seek(Number(event.target.value))} aria-label="Posición de reproducción" /><span>{formatDuration(playerDuration)}</span></div></div>
          <button className="player-control player-share" onClick={() => void shareLink(activeTrack.title, `/#track=${activeTrack.id}`)} aria-label="Compartir canción">↗</button>
          <button className="player-close" onClick={() => { player.stop(); setActiveTrackId(null); setActiveTrack(null); }} aria-label="Cerrar reproductor">×</button>
        </div>
      )}
    </section>
  </main></div>;
}
