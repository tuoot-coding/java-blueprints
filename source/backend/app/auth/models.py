"""Доменные модели аутентификации."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType

UserId = NewType("UserId", str)
SessionId = NewType("SessionId", str)


class AuthTokenPurpose(StrEnum):
    EMAIL_VERIFY = "email_verify"
    PASSWORD_RESET = "password_reset"


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UserId
    email: str
    email_normalized: str
    username: str
    username_normalized: str
    role: UserRole
    password_hash: str
    email_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None


@dataclass(frozen=True, slots=True)
class SessionRecord:
    id_hash: str
    user_id: UserId
    csrf_hash: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


@dataclass(frozen=True, slots=True)
class AuthTokenRecord:
    id: str
    user_id: UserId
    purpose: AuthTokenPurpose
    token_hash: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
