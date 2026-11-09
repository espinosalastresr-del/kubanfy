"""Auth-related request and response schemas."""

from __future__ import annotations

from datetime import datetime
import re
import unicodedata
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


def _validate_bcrypt_password_length(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password cannot exceed bcrypt's 72-byte UTF-8 limit")
    return value


def _validate_auth_password(value: str) -> str:
    has_letter = any(char.isalpha() for char in value)
    has_number_or_symbol = any(
        char.isnumeric() or unicodedata.category(char)[0] in {"P", "S"}
        for char in value
    )
    _validate_bcrypt_password_length(value)
    if not has_letter or not has_number_or_symbol:
        raise ValueError(
            "Password must contain at least one letter and one number or symbol"
        )
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    language: str = Field(default="es", max_length=10)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_auth_password(v)

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be blank")
        return value

    @field_validator("country")
    @classmethod
    def country_upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    device_id: str | None = Field(default=None, max_length=128)
    device_name: str | None = Field(default=None, max_length=120)
    platform: str | None = Field(default=None, max_length=32)

    @field_validator("password")
    @classmethod
    def bcrypt_password_length(cls, value: str) -> str:
        return _validate_bcrypt_password_length(value)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    avatar: str | None
    country: str
    language: str
    status: str
    email_verified: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class AuthContextResponse(BaseModel):
    user: UserResponse
    roles: list[str]
    artist_ids: list[UUID]
    is_artist: bool
    is_admin: bool


class RefreshRequest(BaseModel):
    refresh_token: str
    device_id: str | None = Field(default=None, max_length=128)


class DeviceResponse(BaseModel):
    id: UUID
    device_id: str
    name: str | None
    platform: str | None
    os_version: str | None
    app_version: str | None
    status: str
    identity_verified: bool
    created_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: UUID
    status: str
    ip_country: str | None
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


class PasswordResetRequest(BaseModel):
    email: EmailStr


class EmailVerificationRequest(BaseModel):
    email: EmailStr


class EmailVerificationConfirmRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_auth_password(v)


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=2, max_length=2)
    language: str = Field(min_length=2, max_length=10)

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be blank")
        return value

    @field_validator("country")
    @classmethod
    def profile_country_upper(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", normalized):
            raise ValueError("Country must be a two-letter ISO code")
        return normalized

    @field_validator("language")
    @classmethod
    def profile_language_supported(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"es", "en"}:
            raise ValueError("Language must be es or en")
        return normalized
