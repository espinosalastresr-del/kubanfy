import { FormEvent, useState } from "react";
import { ApiError, requestPasswordReset } from "./api";

function LogoMark() {
  return (
    <div className="logo-mark" aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
  );
}

type Props = {
  initialEmail?: string;
  onBack: () => void;
};

export function ForgotPasswordView({ initialEmail = "", onBack }: Props) {
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!email.includes("@")) {
      setError("Introduce un correo válido.");
      return;
    }
    setBusy(true);
    try {
      await requestPasswordReset(email);
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError && err.status >= 500) {
        setError("No pudimos enviar el correo ahora. Inténtalo más tarde.");
      } else if (!navigator.onLine) {
        setError("Sin conexión. Comprueba la red e inténtalo de nuevo.");
      } else {
        setDone(true);
      }
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
          <LogoMark />
          <span>KubanFy</span>
        </div>
        <div className="glass auth-card">
          <div className="auth-heading">
            <span className="eyebrow">RECUPERAR ACCESO</span>
            <h1>Restablecer <em>contraseña</em></h1>
            <p>
              Te enviaremos un enlace si existe una cuenta con ese correo. Revisa también spam.
            </p>
          </div>
          {done ? (
            <div>
              <p className="form-status is-notice" role="status">
                Si hay una cuenta asociada a <strong>{email.trim()}</strong>, recibirás instrucciones en
                breve.
              </p>
              <button type="button" className="primary-button" onClick={onBack} style={{ marginTop: 16 }}>
                Volver al inicio de sesión
              </button>
            </div>
          ) : (
            <form onSubmit={submit} noValidate>
              <label className="field">
                <span>Correo electrónico</span>
                <input
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  value={email}
                  onChange={(ev) => setEmail(ev.target.value)}
                  placeholder="tu@email.com"
                  required
                />
              </label>
              {error && (
                <div className="form-status" role="alert">
                  {error}
                </div>
              )}
              <button className="primary-button" type="submit" disabled={busy} style={{ marginTop: 16 }}>
                {busy ? "Enviando…" : "Enviar enlace"}
              </button>
              <p className="signup-prompt" style={{ marginTop: 16 }}>
                <a
                  href="#login"
                  onClick={(ev) => {
                    ev.preventDefault();
                    onBack();
                  }}
                >
                  ← Volver al login
                </a>
              </p>
            </form>
          )}
        </div>
      </section>
    </main>
  );
}
