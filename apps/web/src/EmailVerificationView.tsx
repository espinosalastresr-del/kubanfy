import { FormEvent, useEffect, useState } from "react";
import { ApiError, confirmEmailVerification, requestEmailVerification } from "./api";

export function EmailVerificationView({
  initialEmail,
  token,
  onBack,
  onVerified,
}: {
  initialEmail: string;
  token: string | null;
  onBack: () => void;
  onVerified: () => void;
}) {
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [verified, setVerified] = useState(false);
  const [message, setMessage] = useState(initialEmail ? "Revisa tu bandeja de entrada y la carpeta de correo no deseado. Si no encuentras el enlace, puedes solicitar otro." : "");
  const [error, setError] = useState("");

  useEffect(() => {
    setEmail(initialEmail);
  }, [initialEmail]);

  useEffect(() => {
    if (!token) return;
    let active = true;
    setBusy(true);
    setError("");
    void confirmEmailVerification(token)
      .then((result) => {
        if (!active) return;
        setVerified(true);
        setMessage(result.message);
      })
      .catch((cause) => {
        if (!active) return;
        const apiError = cause instanceof ApiError ? cause : null;
        setError(apiError?.code === "EMAIL_VERIFICATION_INVALID"
          ? "Este enlace ha caducado o ya fue utilizado. Solicita uno nuevo."
          : "No pudimos verificar el correo. Comprueba tu conexión e inténtalo otra vez.");
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => { active = false; };
  }, [token]);

  async function resend(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!email.trim() || !email.includes("@")) {
      setError("Introduce un correo electrónico válido.");
      return;
    }
    setBusy(true);
    try {
      const result = await requestEmailVerification(email);
      setMessage(result.message);
    } catch {
      setError("No pudimos procesar la solicitud. Espera unos minutos e inténtalo de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <section className="auth-shell">
        <div className="auth-brand">
          <div className="logo-mark" aria-hidden="true"><span /><span /><span /></div>
          <span>KubanFy</span>
        </div>
        <div className="glass auth-card">
          <div className="auth-heading">
            <span className="eyebrow">PROTEGE TU CUENTA</span>
            <h1>{verified ? <>Correo <em>confirmado.</em></> : <>Confirma tu <em>correo.</em></>}</h1>
            <p>
              {verified
                ? "Tu dirección de correo ya está verificada. Puedes iniciar sesión y empezar a escuchar."
                : "Necesitamos confirmar que esta dirección te pertenece antes de activar tu cuenta."}
            </p>
          </div>

          {busy && token ? (
            <div className="form-status" role="status">Verificando tu enlace…</div>
          ) : verified ? (
            <>
              <div className="form-status is-notice" role="status">{message}</div>
              <button className="primary-button login-button" type="button" onClick={onVerified}>
                <span>Ir a iniciar sesión</span><span className="button-arrow">→</span>
              </button>
            </>
          ) : (
            <form onSubmit={resend} noValidate>
              <label className="field">
                <span>Correo electrónico</span>
                <input
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="tu@email.com"
                  required
                />
              </label>
              {message && <div className="form-status is-notice" role="status">{message}</div>}
              {error && <div className="form-status" role="alert">{error}</div>}
              <button className="primary-button login-button" type="submit" disabled={busy} aria-busy={busy}>
                {busy ? "Enviando…" : "Enviar enlace de verificación"}
              </button>
            </form>
          )}
          <div className="auth-divider"><span>o</span></div>
          <p className="signup-prompt">
            <a href="#login" onClick={(event) => { event.preventDefault(); onBack(); }}>← Volver a iniciar sesión</a>
          </p>
        </div>
        <p className="auth-footnote">El enlace de verificación tiene una duración limitada y solo puede utilizarse una vez.</p>
      </section>
    </main>
  );
}
