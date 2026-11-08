import { FormEvent, useState } from "react";
import { ApiError, register } from "./api";
import { isValidEmail, normalizeEmail, passwordValidationError } from "./authValidation";

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

export function RegisterView({ onBack, onRegistered }: { onBack: () => void; onRegistered: (email: string) => void }) {
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
    if (!name.trim() || !isValidEmail(email) || passwordValidationError(password) || password !== confirmation) return;
    setBusy(true);
    try {
      await register(normalizeEmail(email), password, name.trim());
      onRegistered(normalizeEmail(email));
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError("Este correo ya está registrado. Inicia sesión o recupera tu contraseña.");
      } else if (e instanceof ApiError && e.status === 422) {
        setError("Revisa los datos: usa un correo válido y una contraseña de al menos 8 caracteres con letras y números o símbolos.");
      } else {
        setError("No pudimos crear la cuenta. Inténtalo de nuevo.");
      }
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
            <input type="text" autoComplete="name" value={name} onChange={e => setName(e.target.value)} placeholder="Tu nombre" maxLength={120} aria-invalid={submitted && !name.trim()} required />
            {submitted && !name.trim() && <small>Introduce tu nombre.</small>}
          </label>
          <label className="field">
            <span>Correo electrónico</span>
            <input type="email" inputMode="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="tu@email.com" maxLength={254} aria-invalid={submitted && !isValidEmail(email)} required />
            {submitted && !isValidEmail(email) && <small>Introduce un correo electrónico válido.</small>}
          </label>
          <label className="field">
            <span>Contraseña</span>
            <div className="password-field">
              <input type={showPassword ? "text" : "password"} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Mínimo 8 caracteres" maxLength={128} aria-invalid={submitted && !!passwordValidationError(password)} required />
              <button type="button" className="icon-button" onClick={() => setShowPassword(v => !v)} aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}><EyeIcon hidden={showPassword} /></button>
            </div>
            {submitted && passwordValidationError(password) && <small>{passwordValidationError(password)}</small>}
          </label>
          <label className="field">
            <span>Repetir contraseña</span>
            <input type={showPassword ? "text" : "password"} autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} placeholder="Repite tu contraseña" maxLength={128} aria-invalid={submitted && password !== confirmation} required />
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
