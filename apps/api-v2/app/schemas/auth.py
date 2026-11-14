import re
from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    age: int = Field(ge=1, le=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    password_confirmation: str = Field(min_length=12, max_length=128)
    country_of_origin: str = Field(min_length=2, max_length=2)
    accept_terms: bool

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Introduce un nombre completo válido.")
        return normalized

    @field_validator("country_of_origin")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", normalized):
            raise ValueError("El país debe utilizar un código ISO 3166-1 alpha-2.")
        return normalized

    @field_validator("accept_terms")
    @classmethod
    def require_terms_acceptance(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Debes aceptar el acuerdo de uso para crear una cuenta.")
        return value

    @model_validator(mode="after")
    def passwords_must_match(self) -> Self:
        if self.password != self.password_confirmation:
            raise ValueError("Las contraseñas no coinciden.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = True


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    age: int
    email: EmailStr
    country_of_origin: str
    preferred_content_country: str | None
    content_country_mode: str
    created_at: datetime


class AuthResponse(BaseModel):
    message: str
    user: UserRead
    terms_version: str | None = None
    terms_status: str | None = None


class SessionRead(BaseModel):
    id: UUID
    expires_at: datetime
    detected_country: str | None
    content_country: str | None


class MeResponse(BaseModel):
    user: UserRead
    session: SessionRead
