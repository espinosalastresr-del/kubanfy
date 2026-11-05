"""Auth-related request and response schemas."""

from __future__ import annotations

from datetime import datetime
import re
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    language: str = Field(default="es", max_length=10)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v.isdigit() or v.isalpha():
            raise ValueError("Password must contain letters and numbers or symbols")
        return v

    @field_validator("country")
    @classmethod
    def country_upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_id: str | None = Field(default=None, max_length=128)
    device_name: str | None = Field(default=None, max_length=120)
    platform: str | None = Field(default=None, max_length=32)


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


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v.isdigit() or v.isalpha():
            raise ValueError("Password must contain letters and numbers or symbols")
        return v


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
