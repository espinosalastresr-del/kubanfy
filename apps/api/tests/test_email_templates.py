"""Shared transactional email template tests."""
from __future__ import annotations

from app.services.email_templates import email_verification_email, password_reset_email


def test_password_reset_template_has_html_and_plain_text_alternatives() -> None:
    url = "https://kubanfy.example/#reset_token=abc123"

    content = password_reset_email(url)

    assert content.subject == "Restablece tu contraseña de KubanFy"
    assert "Crear una nueva contraseña" in content.text_body
    assert url in content.text_body
    assert 'href="https://kubanfy.example/#reset_token=abc123"' in content.html_body
    assert "width=device-width, initial-scale=1" in content.html_body
    assert "prefers-color-scheme: dark" in content.html_body
    assert "<script" not in content.html_body.lower()


def test_verification_template_has_action_and_security_context() -> None:
    url = "https://kubanfy.example/?verify_token=abc123"

    content = email_verification_email(url)

    assert content.subject == "Confirma tu correo electrónico — KubanFy"
    assert "Verificar mi correo" in content.text_body
    assert url in content.text_body
    assert "No se activará sin confirmar" in content.text_body
    assert "Verificar mi correo" in content.html_body


def test_template_escapes_untrusted_action_url_in_html() -> None:
    malicious_url = 'https://kubanfy.example/?next="><script>alert(1)</script>'

    content = password_reset_email(malicious_url)

    assert "<script>" not in content.html_body
    assert "&lt;script&gt;" in content.html_body
    assert "&quot;" in content.html_body
    assert malicious_url in content.text_body
