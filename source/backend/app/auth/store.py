"""Контракт хранилища пользователей, сессий и auth-токенов."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.auth.models import (
    AuthTokenPurpose,
    AuthTokenRecord,
    SessionRecord,
    UserId,
    UserRecord,
    UserRole,
)


class AuthStore(Protocol):
    def init_schema(self) -> None: ...

    def create_user(
        self,
        *,
        email: str,
        email_normalized: str,
        username: str,
        username_normalized: str,
        role: UserRole,
        password_hash: str,
    ) -> UserRecord: ...

    def get_user_by_id(self, user_id: UserId) -> UserRecord | None: ...

    def get_user_by_email_normalized(self, email_normalized: str) -> UserRecord | None: ...

    def get_user_by_username_normalized(
        self, username_normalized: str
    ) -> UserRecord | None: ...

    def update_password_hash(self, user_id: UserId, password_hash: str) -> None: ...

    def update_role(self, user_id: UserId, role: UserRole) -> None: ...

    def mark_email_verified(self, user_id: UserId, verified_at: datetime) -> None: ...

    def create_session(
        self,
        *,
        id_hash: str,
        user_id: UserId,
        csrf_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> SessionRecord: ...

    def get_session_by_hash(self, id_hash: str) -> SessionRecord | None: ...

    def touch_session(
        self, id_hash: str, *, last_seen_at: datetime, expires_at: datetime
    ) -> None: ...

    def revoke_session(self, id_hash: str, *, revoked_at: datetime) -> None: ...

    def revoke_user_sessions(self, user_id: UserId, *, revoked_at: datetime) -> None: ...

    def create_auth_token(
        self,
        *,
        token_id: str,
        user_id: UserId,
        purpose: AuthTokenPurpose,
        token_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> AuthTokenRecord: ...

    def get_auth_token_by_hash(
        self, token_hash: str, *, purpose: AuthTokenPurpose
    ) -> AuthTokenRecord | None: ...

    def mark_auth_token_used(self, token_id: str, *, used_at: datetime) -> None: ...

    def invalidate_auth_tokens(
        self, user_id: UserId, *, purpose: AuthTokenPurpose, at: datetime
    ) -> None: ...

    def get_rate_limit(self, bucket_key: str) -> tuple[int, datetime, datetime | None] | None: ...

    def upsert_rate_limit(
        self,
        bucket_key: str,
        *,
        fail_count: int,
        window_started_at: datetime,
        blocked_until: datetime | None,
    ) -> None: ...

    def clear_rate_limit(self, bucket_key: str) -> None: ...
