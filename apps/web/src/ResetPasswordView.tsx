import { FormEvent, useState } from "react";
import { ApiError, confirmPasswordReset } from "./api";

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
  token: string;
  onDone: () => void;
};

export function ResetPasswordView({ token, onDone }: Props) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("La contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (password !== confirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setBusy(true);
    try {
      await confirmPasswordReset(token, password);
      setOk(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.status === 400 || err.status === 404
            ? "El enlace no es válido o ha caducado. Solicita uno nuevo."
            : err.message || "No se pudo restablecer la contraseña.",
        );
      } else {
        setError("No se pudo restablecer la contraseña.");
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
            <span className="eyebrow">NUEVA CONTRASEÑA</span>
            <h1>Elige una <em>nueva clave</em></h1>
          </div>
          {ok ? (
            <div>
              <p className="form-status is-notice" role="status">
                Contraseña actualizada. Ya puedes iniciar sesión.
              </p>
              <button type="button" className="primary-button" onClick={onDone} style={{ marginTop: 16 }}>
                Ir al login
              </button>
            </div>
          ) : (
            <form onSubmit={submit}>
              <label className="field">
                <span>Nueva contraseña</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(ev) => setPassword(ev.target.value)}
                  required
                  minLength={8}
                />
              </label>
              <label className="field">
                <span>Confirmar</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(ev) => setConfirm(ev.target.value)}
                  required
                  minLength={8}
                />
              </label>
              {error && (
                <div className="form-status" role="alert">
                  {error}
                </div>
              )}
              <button className="primary-button" type="submit" disabled={busy} style={{ marginTop: 16 }}>
                {busy ? "Guardando…" : "Guardar contraseña"}
              </button>
            </form>
          )}
        </div>
      </section>
    </main>
  );
}
