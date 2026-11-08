"""Shared, accessible HTML and plain-text templates for transactional email."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True, slots=True)
class EmailContent:
    """Provider-independent email content with both text and HTML alternatives."""

    subject: str
    text_body: str
    html_body: str


def _render_action_email(
    *,
    subject: str,
    preheader: str,
    heading: str,
    message: str,
    action_label: str,
    action_url: str,
    fallback_label: str,
    security_note: str,
) -> EmailContent:
    """Render a consistent KubanFy action email without external assets or scripts."""
    safe_preheader = escape(preheader)
    safe_heading = escape(heading)
    safe_message = escape(message)
    safe_action_label = escape(action_label)
    safe_action_url = escape(action_url, quote=True)
    safe_fallback_label = escape(fallback_label)
    safe_security_note = escape(security_note)

    text_body = (
        f"{heading}\n\n"
        f"{message}\n\n"
        f"{action_label}: {action_url}\n\n"
        f"{fallback_label}: {action_url}\n\n"
        f"{security_note}\n\n"
        "KubanFy"
    )
    html_body = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>{escape(subject)}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ margin: 0; padding: 0; background: #f3f5f8; }}
    .email-shell {{ width: 100%; padding: 36px 12px; background: #f3f5f8; }}
    .email-card {{ width: 100%; max-width: 560px; margin: 0 auto; background: #ffffff;
      border: 1px solid #e5e9ef; border-radius: 18px; overflow: hidden; }}
    .email-header {{ padding: 28px 36px 18px; }}
    .brand {{ color: #111827; font: 700 22px/1.2 Arial, Helvetica, sans-serif;
      letter-spacing: -0.6px; }}
    .brand-mark {{ color: #0d9488; }}
    .email-content {{ padding: 16px 36px 34px; color: #263244;
      font: 16px/1.65 Arial, Helvetica, sans-serif; }}
    h1 {{ margin: 0 0 14px; color: #111827; font-size: 25px; line-height: 1.25; }}
    p {{ margin: 0 0 18px; }}
    .action {{ display: inline-block; margin: 8px 0 22px; padding: 13px 22px;
      border-radius: 10px; background: #0d9488; color: #ffffff !important;
      font-weight: 700; text-decoration: none; }}
    .fallback {{ overflow-wrap: anywhere; color: #0f766e; font-size: 13px; }}
    .security {{ margin-top: 24px; padding: 14px 16px; border-radius: 10px;
      background: #f1f5f9; color: #475569; font-size: 13px; }}
    .email-footer {{ padding: 20px 36px 26px; border-top: 1px solid #edf0f4;
      color: #64748b; font: 12px/1.6 Arial, Helvetica, sans-serif; }}
    @media (max-width: 480px) {{
      .email-shell {{ padding: 16px 8px !important; }}
      .email-header {{ padding: 24px 22px 14px !important; }}
      .email-content {{ padding: 14px 22px 26px !important; }}
      .email-footer {{ padding: 18px 22px 22px !important; }}
      h1 {{ font-size: 22px !important; }}
    }}
    @media (prefers-color-scheme: dark) {{
      body, .email-shell {{ background: #0b1220 !important; }}
      .email-card {{ background: #111827 !important; border-color: #263244 !important; }}
      .brand, h1, .email-content {{ color: #f8fafc !important; }}
      .email-content {{ color: #dbe4ef !important; }}
      .email-footer {{ border-color: #263244 !important; color: #94a3b8 !important; }}
      .security {{ background: #1e293b !important; color: #cbd5e1 !important; }}
    }}
  </style>
</head>
<body>
  <div class="email-shell">
    <main class="email-card" role="article" aria-label="Mensaje de KubanFy">
      <header class="email-header">
        <div class="brand">Kuban<span class="brand-mark">Fy</span></div>
      </header>
      <section class="email-content">
        <span hidden>{safe_preheader}</span>
        <h1>{safe_heading}</h1>
        <p>{safe_message}</p>
        <p><a class="action" href="{safe_action_url}">{safe_action_label}</a></p>
        <p class="fallback">{safe_fallback_label}:<br><a href="{safe_action_url}">{safe_action_url}</a></p>
        <div class="security">{safe_security_note}</div>
      </section>
      <footer class="email-footer">
        Este mensaje se ha enviado automáticamente. No respondas a este correo.<br>
        © KubanFy
      </footer>
    </main>
  </div>
</body>
</html>"""
    return EmailContent(subject=subject, text_body=text_body, html_body=html_body)


def password_reset_email(action_url: str) -> EmailContent:
    """Build the password-reset message."""
    return _render_action_email(
        subject="Restablece tu contraseña de KubanFy",
        preheader="Recibimos una solicitud para cambiar la contraseña de tu cuenta.",
        heading="Restablece tu contraseña",
        message="Recibimos una solicitud para cambiar la contraseña de tu cuenta de KubanFy.",
        action_label="Crear una nueva contraseña",
        action_url=action_url,
        fallback_label="Si el botón no funciona, copia este enlace en tu navegador",
        security_note=(
            "Si no solicitaste este cambio, ignora este mensaje. Tu contraseña no cambiará "
            "hasta que completes el proceso."
        ),
    )


def email_verification_email(action_url: str) -> EmailContent:
    """Build the account email-verification message."""
    return _render_action_email(
        subject="Confirma tu correo electrónico — KubanFy",
        preheader="Confirma tu correo para activar tu cuenta de KubanFy.",
        heading="Confirma tu correo electrónico",
        message="Gracias por crear tu cuenta de KubanFy. Confirma que esta dirección te pertenece.",
        action_label="Verificar mi correo",
        action_url=action_url,
        fallback_label="Si el botón no funciona, copia este enlace en tu navegador",
        security_note=(
            "Si no creaste esta cuenta, puedes ignorar este mensaje. No se activará sin "
            "confirmar la dirección de correo."
        ),
    )
