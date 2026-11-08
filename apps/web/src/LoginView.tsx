import { FormEvent, useEffect, useState } from "react";
import { ApiError } from "./api";
import { isInstallAvailable, isStandaloneDisplay, promptPwaInstall, subscribeInstallAvailable } from "./installPrompt";

function EyeIcon({ hidden }: { hidden: boolean }) {
  return hidden ? (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.7a2 2 0 0 0 2.7 2.7M9.9 5.2A10.8 10.8 0 0 1 12 5c5 0 8.5 4.1 9.5 6a17.7 17.7 0 0 1-3.1 3.7M6.2 6.2C3.9 7.7 2.5 10 2.5 12c1 1.9 4.5 6 9.5 6 1.7 0 3.2-.4 4.5-1.1" /></svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12S6 6 12 6s9.5 6 9.5 6S18 18 12 18s-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.8" /></svg>
  );
}

function LogoMark() {
  return <div className="logo-mark" aria-hidden="true"><span /><span /><span /></div>;
}

export function LoginView({ onLogin, onRegister, onForgot, onVerifyEmail, initialEmail }: { onLogin: (email: string, password: string) => Promise<void>; onRegister: () => void; onForgot?: () => void; onVerifyEmail?: (email: string) => void; initialEmail: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [notice, setNotice] = useState("");
  const [authError, setAuthError] = useState("");
  const [needsVerification, setNeedsVerification] = useState(false);
  const [installAvailable, setInstallAvailable] = useState(isInstallAvailable());
  const [installGuideOpen, setInstallGuideOpen] = useState(false);
  const [installMessage, setInstallMessage] = useState("");
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) && !(window as Window & { MSStream?: unknown }).MSStream;
  
  useEffect(() => {
    setEmail(initialEmail);
  }, [initialEmail]);

  useEffect(() => subscribeInstallAvailable(setInstallAvailable), []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    setAuthError("");
    setNeedsVerification(false);
    if (!email || !password || !email.includes("@")) return;
    setBusy(true);
    try {
      await onLogin(email.trim(), password);
    } catch (e) {
      const message = e instanceof Error ? e.message : "";
      const status = e instanceof ApiError ? e.status : 0;
      if (status === 403 && e instanceof ApiError && e.code === "EMAIL_NOT_VERIFIED") {
        setNeedsVerification(true);
        setAuthError("Debes verificar tu correo electrónico antes de iniciar sesión.");
      } else if (status === 401 && /invalid email or password/i.test(message)) {
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
              <button type="button" className="icon-button" onClick={() => setShowPassword(v => !v)} aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}>
                <EyeIcon hidden={showPassword} />
              </button>
            </div>
            {submitted && !password && <small>Introduce tu contraseña.</small>}
          </label>

          {authError && <div className="form-status" role="alert">{authError}</div>}
          {needsVerification && <button className="secondary-button" type="button" onClick={() => onVerifyEmail?.(email)}>Verificar mi correo o reenviar el enlace</button>}
          {notice && <div className="form-status is-notice">{notice}</div>}

          <div className="form-meta">
            <a href="#forgot" onClick={e => { e.preventDefault(); onForgot?.(); }}>¿Olvidaste tu contraseña?</a>
          </div>

          <button className={`primary-button login-button${busy ? " is-loading" : ""}`} type="submit" disabled={busy} aria-busy={busy}>
            {busy ? <><span className="button-spinner" aria-hidden="true" /><span>Entrando…</span></> : <><span>Entrar</span><span className="button-arrow">→</span></>}
          </button>
        </form>

        <div className="auth-divider"><span>o</span></div>
        <p className="signup-prompt">¿No tienes cuenta? <a href="#register" onClick={e => { e.preventDefault(); onRegister(); }}>Crear cuenta</a></p>
      </div>

      {!isStandaloneDisplay() && (
        <section className="install-panel" aria-label="Instalar KubanFy">
          <div className="install-panel-copy">
            <strong>Instala KubanFy</strong>
            <span>Acceso directo, pantalla completa y tu música siempre a mano.</span>
          </div>
          {installAvailable ? (
            <button className="secondary-button install-action" onClick={async () => {
              try {
                const outcome = await promptPwaInstall();
                setInstallMessage(outcome === "accepted" ? "KubanFy se está instalando." : "Puedes instalarla cuando quieras desde el menú del navegador.");
              } catch {
                setInstallGuideOpen(true);
              }
            }}>Instalar aplicación</button>
          ) : (
            <button className="secondary-button install-action" onClick={() => setInstallGuideOpen((v) => !v)}>
              Cómo instalar
            </button>
          )}
          {installGuideOpen && (
            <div className="install-guide" role="status">
              {isIOS ? (
                <>
                  <strong>En iPhone o iPad</strong>
                  <ol>
                    <li>Abre esta página en Safari.</li>
                    <li>Pulsa el botón Compartir.</li>
                    <li>Selecciona «Añadir a pantalla de inicio».</li>
                    <li>Confirma con «Añadir».</li>
                  </ol>
                </>
              ) : (
                <>
                  <strong>En Android</strong>
                  <ol>
                    <li>Abre el menú ⋮ de Chrome.</li>
                    <li>Selecciona «Instalar aplicación» o «Añadir a pantalla principal».</li>
                    <li>Confirma la instalación.</li>
                  </ol>
                  <span>Si no aparece la opción, espera a que termine de cargar y vuelve a abrir el menú.</span>
                </>
              )}
            </div>
          )}
          {installMessage && <span className="install-message" role="status">{installMessage}</span>}
        </section>
      )}
      <p className="auth-footnote">Diseñado para consumir menos datos y seguir sonando.</p>
    </section>
  </main>;
}
