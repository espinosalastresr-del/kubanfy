"""Authentication request schema validation tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.auth import PasswordResetConfirmRequest, RegisterRequest


@pytest.mark.parametrize("password", ["passwordonly", "123456789", "!!!!!!!!", "a" * 72 + "1"])
def test_registration_rejects_password_without_letter_and_number_or_symbol(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="person@example.com",
            password=password,
            display_name="Person",
        )


@pytest.mark.parametrize("password", ["Password123", "Clave!Segura", "1234567a", "á" * 35 + "1"])
def test_registration_accepts_password_with_letter_and_number_or_symbol(password: str) -> None:
    request = RegisterRequest(
        email="person@example.com",
        password=password,
        display_name="Person",
    )
    assert request.password == password


@pytest.mark.parametrize("password", ["a" * 72 + "1", "á" * 36 + "1"])
def test_registration_rejects_password_over_bcrypt_byte_limit(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="person@example.com",
            password=password,
            display_name="Person",
        )


def test_registration_rejects_blank_display_name() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="person@example.com",
            password="Password123",
            display_name="   ",
        )


def test_registration_normalizes_display_name_whitespace() -> None:
    request = RegisterRequest(
        email="person@example.com",
        password="Password123",
        display_name="  Ray  ",
    )
    assert request.display_name == "Ray"


@pytest.mark.parametrize("password", ["passwordonly", "123456789", "!!!!!!!!"])
def test_password_reset_uses_the_same_password_policy(password: str) -> None:
    with pytest.raises(ValidationError):
        PasswordResetConfirmRequest(token="x" * 40, new_password=password)


def test_password_reset_accepts_letters_and_symbols() -> None:
    request = PasswordResetConfirmRequest(
        token="x" * 40,
        new_password="Clave!Segura",
    )
    assert request.new_password == "Clave!Segura"
