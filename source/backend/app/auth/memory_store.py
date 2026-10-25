"""In-memory хранилище auth для тестов и локального режима без MySQL."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime

from app.auth.models import (
    AuthTokenPurpose,
    AuthTokenRecord,
    SessionRecord,
    UserId,
    UserRecord,
    UserRole,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _replace_user(user: UserRecord, **changes: object) -> UserRecord:
    data = {
        "id": user.id,
        "email": user.email,
        "email_normalized": user.email_normalized,
        "username": user.username,
        "username_normalized": user.username_normalized,
        "role": user.role,
        "password_hash": user.password_hash,
        "email_verified_at": user.email_verified_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }
    data.update(changes)
    return UserRecord(**data)  # type: ignore[arg-type]


class MemoryAuthStore:
    """Потокобезопасное хранилище в памяти процесса."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._users: dict[str, UserRecord] = {}
        self._users_by_email: dict[str, str] = {}
        self._users_by_username: dict[str, str] = {}
        self._sessions: dict[str, SessionRecord] = {}
        self._tokens: dict[str, AuthTokenRecord] = {}
        self._rate: dict[str, tuple[int, datetime, datetime | None]] = {}

    def init_schema(self) -> None:
        return None

    def create_user(
        self,
        *,
        email: str,
        email_normalized: str,
        username: str,
        username_normalized: str,
        role: UserRole,
        password_hash: str,
    ) -> UserRecord:
        with self._lock:
            if email_normalized in self._users_by_email:
                raise ValueError("email_taken")
            if username_normalized in self._users_by_username:
                raise ValueError("username_taken")
            now = _now()
            user = UserRecord(
                id=UserId(uuid.uuid4().hex),
                email=email,
                email_normalized=email_normalized,
                username=username,
                username_normalized=username_normalized,
                role=role,
                password_hash=password_hash,
                email_verified_at=None,
                created_at=now,
                updated_at=now,
            )
            self._users[user.id] = user
            self._users_by_email[email_normalized] = user.id
            self._users_by_username[username_normalized] = user.id
            return user

    def get_user_by_id(self, user_id: UserId) -> UserRecord | None:
        with self._lock:
            return self._users.get(user_id)

    def get_user_by_email_normalized(self, email_normalized: str) -> UserRecord | None:
        with self._lock:
            user_id = self._users_by_email.get(email_normalized)
            return self._users.get(user_id) if user_id else None

    def get_user_by_username_normalized(
        self, username_normalized: str
    ) -> UserRecord | None:
        with self._lock:
            user_id = self._users_by_username.get(username_normalized)
            return self._users.get(user_id) if user_id else None

    def update_password_hash(self, user_id: UserId, password_hash: str) -> None:
        with self._lock:
            user = self._users[user_id]
            self._users[user_id] = _replace_user(
                user, password_hash=password_hash, updated_at=_now()
            )

    def update_role(self, user_id: UserId, role: UserRole) -> None:
        with self._lock:
            user = self._users[user_id]
            self._users[user_id] = _replace_user(user, role=role, updated_at=_now())

    def mark_email_verified(self, user_id: UserId, verified_at: datetime) -> None:
        with self._lock:
            user = self._users[user_id]
            self._users[user_id] = _replace_user(
                user, email_verified_at=verified_at, updated_at=verified_at
            )

    def create_session(
        self,
        *,
        id_hash: str,
        user_id: UserId,
        csrf_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> SessionRecord:
        with self._lock:
            session = SessionRecord(
                id_hash=id_hash,
                user_id=user_id,
                csrf_hash=csrf_hash,
                created_at=created_at,
                expires_at=expires_at,
                last_seen_at=created_at,
                revoked_at=None,
            )
            self._sessions[id_hash] = session
            return session

    def get_session_by_hash(self, id_hash: str) -> SessionRecord | None:
        with self._lock:
            return self._sessions.get(id_hash)

    def touch_session(
        self, id_hash: str, *, last_seen_at: datetime, expires_at: datetime
    ) -> None:
        with self._lock:
            session = self._sessions[id_hash]
            self._sessions[id_hash] = SessionRecord(
                id_hash=session.id_hash,
                user_id=session.user_id,
                csrf_hash=session.csrf_hash,
                created_at=session.created_at,
                expires_at=expires_at,
                last_seen_at=last_seen_at,
                revoked_at=session.revoked_at,
            )

    def revoke_session(self, id_hash: str, *, revoked_at: datetime) -> None:
        with self._lock:
            session = self._sessions.get(id_hash)
            if session is None:
                return
            self._sessions[id_hash] = SessionRecord(
                id_hash=session.id_hash,
                user_id=session.user_id,
                csrf_hash=session.csrf_hash,
                created_at=session.created_at,
                expires_at=session.expires_at,
                last_seen_at=session.last_seen_at,
                revoked_at=revoked_at,
            )

    def revoke_user_sessions(self, user_id: UserId, *, revoked_at: datetime) -> None:
        with self._lock:
            for key, session in list(self._sessions.items()):
                if session.user_id == user_id and session.revoked_at is None:
                    self._sessions[key] = SessionRecord(
                        id_hash=session.id_hash,
                        user_id=session.user_id,
                        csrf_hash=session.csrf_hash,
                        created_at=session.created_at,
                        expires_at=session.expires_at,
                        last_seen_at=session.last_seen_at,
                        revoked_at=revoked_at,
                    )

    def create_auth_token(
        self,
        *,
        token_id: str,
        user_id: UserId,
        purpose: AuthTokenPurpose,
        token_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> AuthTokenRecord:
        with self._lock:
            record = AuthTokenRecord(
                id=token_id,
                user_id=user_id,
                purpose=purpose,
                token_hash=token_hash,
                created_at=created_at,
                expires_at=expires_at,
                used_at=None,
            )
            self._tokens[token_hash] = record
            return record

    def get_auth_token_by_hash(
        self, token_hash: str, *, purpose: AuthTokenPurpose
    ) -> AuthTokenRecord | None:
        with self._lock:
            record = self._tokens.get(token_hash)
            if record is None or record.purpose != purpose:
                return None
            return record

    def mark_auth_token_used(self, token_id: str, *, used_at: datetime) -> None:
        with self._lock:
            for key, record in list(self._tokens.items()):
                if record.id == token_id:
                    self._tokens[key] = AuthTokenRecord(
                        id=record.id,
                        user_id=record.user_id,
                        purpose=record.purpose,
                        token_hash=record.token_hash,
                        created_at=record.created_at,
                        expires_at=record.expires_at,
                        used_at=used_at,
                    )

    def invalidate_auth_tokens(
        self, user_id: UserId, *, purpose: AuthTokenPurpose, at: datetime
    ) -> None:
        with self._lock:
            for key, record in list(self._tokens.items()):
                if (
                    record.user_id == user_id
                    and record.purpose == purpose
                    and record.used_at is None
                ):
                    self._tokens[key] = AuthTokenRecord(
                        id=record.id,
                        user_id=record.user_id,
                        purpose=record.purpose,
                        token_hash=record.token_hash,
                        created_at=record.created_at,
                        expires_at=record.expires_at,
                        used_at=at,
                    )

    def get_rate_limit(self, bucket_key: str) -> tuple[int, datetime, datetime | None] | None:
        with self._lock:
            return self._rate.get(bucket_key)

    def upsert_rate_limit(
        self,
        bucket_key: str,
        *,
        fail_count: int,
        window_started_at: datetime,
        blocked_until: datetime | None,
    ) -> None:
        with self._lock:
            self._rate[bucket_key] = (fail_count, window_started_at, blocked_until)

    def clear_rate_limit(self, bucket_key: str) -> None:
        with self._lock:
            self._rate.pop(bucket_key, None)
