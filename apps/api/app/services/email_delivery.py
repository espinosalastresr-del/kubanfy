"""Small transactional email adapter for configured providers."""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import EmailProviderType, Settings, get_settings


class EmailDeliveryError(RuntimeError):
    """Raised when a configured email provider cannot deliver a message."""


class EmailDeliveryService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        provider = self.settings.email_provider
        if provider == EmailProviderType.RESEND:
            await self._send_resend(recipient, subject, text_body, html_body)
        elif provider == EmailProviderType.BREVO:
            await self._send_brevo(recipient, subject, text_body, html_body)
        elif provider == EmailProviderType.SMTP:
            await asyncio.to_thread(self._send_smtp, recipient, subject, text_body, html_body)
        else:
            raise EmailDeliveryError("Transactional email provider is not configured")

    async def _send_resend(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        if not self.settings.resend_api_key:
            raise EmailDeliveryError("RESEND_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.settings.resend_api_key}"},
                json={
                    "from": self.settings.email_from,
                    "to": [recipient],
                    "subject": subject,
                    "text": text_body,
                    "html": html_body,
                },
            )
        if response.is_error:
            raise EmailDeliveryError(f"Resend rejected email ({response.status_code})")

    async def _send_brevo(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        if not self.settings.brevo_api_key:
            raise EmailDeliveryError("BREVO_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": self.settings.brevo_api_key},
                json={
                    "sender": {"email": self.settings.email_from},
                    "to": [{"email": recipient}],
                    "subject": subject,
                    "textContent": text_body,
                    "htmlContent": html_body,
                },
            )
        if response.is_error:
            raise EmailDeliveryError(f"Brevo rejected email ({response.status_code})")

    def _send_smtp(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        if not self.settings.smtp_host:
            raise EmailDeliveryError("SMTP_HOST is not configured")
        message = EmailMessage()
        message["From"] = self.settings.email_from
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")
        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                if self.settings.smtp_user:
                    smtp.login(self.settings.smtp_user, self.settings.smtp_password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError("SMTP delivery failed") from exc
