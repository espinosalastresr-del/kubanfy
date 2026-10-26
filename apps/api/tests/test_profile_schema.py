"""Validation tests for editable account profile fields."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import ProfileUpdateRequest


def test_profile_update_normalizes_display_name_country_and_language():
    profile = ProfileUpdateRequest(display_name="  Ray  ", country="cu", language="ES")
    assert profile.display_name == "Ray"
    assert profile.country == "CU"
    assert profile.language == "es"


@pytest.mark.parametrize("country", ["C1", "CUB", "U", ""])
def test_profile_update_rejects_invalid_country_codes(country):
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(display_name="Ray", country=country, language="es")


@pytest.mark.parametrize("language", ["fr", "es-MX", "", "123"])
def test_profile_update_rejects_unsupported_languages(language):
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(display_name="Ray", country="CU", language=language)


def test_profile_update_rejects_blank_display_name():
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(display_name="   ", country="CU", language="es")
