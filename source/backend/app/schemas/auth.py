"""Схемы HTTP API аутентификации."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

UserRoleLiteral = Literal["user", "admin"]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=256)
    # На этапе разработки роль выбирает сам пользователь.
    role: UserRoleLiteral = "user"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=16, max_length=256)


class ResendVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Временная возможность смены роли на этапе разработки.
    role: UserRoleLiteral


class AuthMessageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    message: str


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    username: str
    role: UserRoleLiteral
    email_verified: bool
    created_at: datetime


class LoginResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user: AuthUserResponse
    csrf_token: str
    expires_at: datetime
