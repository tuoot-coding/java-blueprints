"""MySQL-хранилище пользователей, сессий и токенов аутентификации."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote, urlparse

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from app.auth.models import (
    AuthTokenPurpose,
    AuthTokenRecord,
    SessionRecord,
    UserId,
    UserRecord,
    UserRole,
)

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id CHAR(32) NOT NULL PRIMARY KEY,
        email VARCHAR(320) NOT NULL,
        email_normalized VARCHAR(320) NOT NULL,
        username VARCHAR(32) NOT NULL,
        username_normalized VARCHAR(32) NOT NULL,
        role VARCHAR(16) NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        email_verified_at DATETIME(6) NULL,
        created_at DATETIME(6) NOT NULL,
        updated_at DATETIME(6) NOT NULL,
        UNIQUE KEY uq_users_email_normalized (email_normalized),
        UNIQUE KEY uq_users_username_normalized (username_normalized)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id_hash CHAR(64) NOT NULL PRIMARY KEY,
        user_id CHAR(32) NOT NULL,
        csrf_hash CHAR(64) NOT NULL,
        created_at DATETIME(6) NOT NULL,
        expires_at DATETIME(6) NOT NULL,
        last_seen_at DATETIME(6) NOT NULL,
        revoked_at DATETIME(6) NULL,
        KEY idx_sessions_user (user_id),
        CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_tokens (
        id CHAR(32) NOT NULL PRIMARY KEY,
        user_id CHAR(32) NOT NULL,
        purpose VARCHAR(32) NOT NULL,
        token_hash CHAR(64) NOT NULL,
        created_at DATETIME(6) NOT NULL,
        expires_at DATETIME(6) NOT NULL,
        used_at DATETIME(6) NULL,
        UNIQUE KEY uq_auth_tokens_hash (token_hash),
        KEY idx_auth_tokens_user_purpose (user_id, purpose),
        CONSTRAINT fk_auth_tokens_user FOREIGN KEY (user_id) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_rate_limits (
        bucket_key VARCHAR(191) NOT NULL PRIMARY KEY,
        fail_count INT NOT NULL,
        window_started_at DATETIME(6) NOT NULL,
        blocked_until DATETIME(6) NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
)


def parse_mysql_dsn(dsn: str) -> dict[str, Any]:
    """Разбирает mysql://user:pass@host:port/db в параметры PyMySQL."""
    normalized = dsn
    for prefix in ("mysql+pymysql://", "mysql://"):
        if normalized.startswith(prefix):
            normalized = "mysql://" + normalized[len(prefix) :]
            break
    parsed = urlparse(normalized)
    if parsed.scheme != "mysql" or not parsed.hostname or not parsed.path.lstrip("/"):
        raise ValueError("AUTH_MYSQL_DSN должен иметь вид mysql://user:pass@host:3306/dbname")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": parsed.path.lstrip("/"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
    }


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class MysqlAuthStore:
    """Подключение к MySQL на каждый вызов (пул не обязателен для MVP)."""

    def __init__(self, dsn: str) -> None:
        self._connect_kwargs = parse_mysql_dsn(dsn)

    @contextmanager
    def _session(self) -> Iterator[Connection]:
        connection = pymysql.connect(**self._connect_kwargs)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def init_schema(self) -> None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                for statement in _SCHEMA_STATEMENTS:
                    cursor.execute(statement)
                _ensure_user_profile_columns(cursor)

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
        user_id = UserId(uuid.uuid4().hex)
        now = datetime.now(UTC)
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (
                        id, email, email_normalized, username, username_normalized,
                        role, password_hash, email_verified_at, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, %s)
                    """,
                    (
                        user_id,
                        email,
                        email_normalized,
                        username,
                        username_normalized,
                        role.value,
                        password_hash,
                        now,
                        now,
                    ),
                )
        return UserRecord(
            id=user_id,
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

    def get_user_by_id(self, user_id: UserId) -> UserRecord | None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                row = cursor.fetchone()
        return _user_from_row(row) if row else None

    def get_user_by_email_normalized(self, email_normalized: str) -> UserRecord | None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM users WHERE email_normalized = %s",
                    (email_normalized,),
                )
                row = cursor.fetchone()
        return _user_from_row(row) if row else None

    def get_user_by_username_normalized(
        self, username_normalized: str
    ) -> UserRecord | None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM users WHERE username_normalized = %s",
                    (username_normalized,),
                )
                row = cursor.fetchone()
        return _user_from_row(row) if row else None

    def update_password_hash(self, user_id: UserId, password_hash: str) -> None:
        now = datetime.now(UTC)
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
                    (password_hash, now, user_id),
                )

    def update_role(self, user_id: UserId, role: UserRole) -> None:
        now = datetime.now(UTC)
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET role = %s, updated_at = %s WHERE id = %s",
                    (role.value, now, user_id),
                )

    def mark_email_verified(self, user_id: UserId, verified_at: datetime) -> None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE users
                    SET email_verified_at = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (verified_at, verified_at, user_id),
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
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO sessions
                    (id_hash, user_id, csrf_hash, created_at, expires_at, last_seen_at, revoked_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NULL)
                    """,
                    (id_hash, user_id, csrf_hash, created_at, expires_at, created_at),
                )
        return SessionRecord(
            id_hash=id_hash,
            user_id=user_id,
            csrf_hash=csrf_hash,
            created_at=created_at,
            expires_at=expires_at,
            last_seen_at=created_at,
            revoked_at=None,
        )

    def get_session_by_hash(self, id_hash: str) -> SessionRecord | None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM sessions WHERE id_hash = %s", (id_hash,))
                row = cursor.fetchone()
        return _session_from_row(row) if row else None

    def touch_session(self, id_hash: str, *, last_seen_at: datetime, expires_at: datetime) -> None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE sessions
                    SET last_seen_at = %s, expires_at = %s
                    WHERE id_hash = %s AND revoked_at IS NULL
                    """,
                    (last_seen_at, expires_at, id_hash),
                )

    def revoke_session(self, id_hash: str, *, revoked_at: datetime) -> None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE sessions SET revoked_at = %s
                    WHERE id_hash = %s AND revoked_at IS NULL
                    """,
                    (revoked_at, id_hash),
                )

    def revoke_user_sessions(self, user_id: UserId, *, revoked_at: datetime) -> None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE sessions SET revoked_at = %s
                    WHERE user_id = %s AND revoked_at IS NULL
                    """,
                    (revoked_at, user_id),
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
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO auth_tokens
                    (id, user_id, purpose, token_hash, created_at, expires_at, used_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NULL)
                    """,
                    (token_id, user_id, purpose.value, token_hash, created_at, expires_at),
                )
        return AuthTokenRecord(
            id=token_id,
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            created_at=created_at,
            expires_at=expires_at,
            used_at=None,
        )

    def get_auth_token_by_hash(
        self, token_hash: str, *, purpose: AuthTokenPurpose
    ) -> AuthTokenRecord | None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM auth_tokens
                    WHERE token_hash = %s AND purpose = %s
                    """,
                    (token_hash, purpose.value),
                )
                row = cursor.fetchone()
        return _token_from_row(row) if row else None

    def mark_auth_token_used(self, token_id: str, *, used_at: datetime) -> None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auth_tokens SET used_at = %s WHERE id = %s AND used_at IS NULL",
                    (used_at, token_id),
                )

    def invalidate_auth_tokens(
        self, user_id: UserId, *, purpose: AuthTokenPurpose, at: datetime
    ) -> None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth_tokens SET used_at = %s
                    WHERE user_id = %s AND purpose = %s AND used_at IS NULL
                    """,
                    (at, user_id, purpose.value),
                )

    def get_rate_limit(self, bucket_key: str) -> tuple[int, datetime, datetime | None] | None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT fail_count, window_started_at, blocked_until
                    FROM auth_rate_limits WHERE bucket_key = %s
                    """,
                    (bucket_key,),
                )
                row = cursor.fetchone()
        if not row:
            return None
        return (
            int(row["fail_count"]),
            _as_utc(row["window_started_at"]) or datetime.now(UTC),
            _as_utc(row["blocked_until"]),
        )

    def upsert_rate_limit(
        self,
        bucket_key: str,
        *,
        fail_count: int,
        window_started_at: datetime,
        blocked_until: datetime | None,
    ) -> None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO auth_rate_limits
                    (bucket_key, fail_count, window_started_at, blocked_until)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        fail_count = VALUES(fail_count),
                        window_started_at = VALUES(window_started_at),
                        blocked_until = VALUES(blocked_until)
                    """,
                    (bucket_key, fail_count, window_started_at, blocked_until),
                )

    def clear_rate_limit(self, bucket_key: str) -> None:
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM auth_rate_limits WHERE bucket_key = %s",
                    (bucket_key,),
                )


def _ensure_user_profile_columns(cursor: Any) -> None:
    """Добавляет username/role к уже созданной таблице users (dev-миграция)."""
    cursor.execute("SHOW COLUMNS FROM users")
    existing = {str(row["Field"]) for row in cursor.fetchall()}
    alterations: list[str] = []
    if "username" not in existing:
        alterations.append(
            "ADD COLUMN username VARCHAR(32) NOT NULL DEFAULT '' AFTER email_normalized"
        )
    if "username_normalized" not in existing:
        alterations.append(
            "ADD COLUMN username_normalized VARCHAR(32) NOT NULL DEFAULT '' "
            "AFTER username"
        )
    if "role" not in existing:
        alterations.append(
            "ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'user' AFTER username_normalized"
        )
    for clause in alterations:
        cursor.execute(f"ALTER TABLE users {clause}")
    if "username_normalized" not in existing:
        try:
            cursor.execute(
                "ALTER TABLE users ADD UNIQUE KEY uq_users_username_normalized "
                "(username_normalized)"
            )
        except pymysql.err.OperationalError:
            pass


def _user_from_row(row: dict[str, Any]) -> UserRecord:
    username = str(row.get("username") or "")
    username_normalized = str(row.get("username_normalized") or username.lower())
    role_raw = str(row.get("role") or UserRole.USER.value)
    try:
        role = UserRole(role_raw)
    except ValueError:
        role = UserRole.USER
    return UserRecord(
        id=UserId(str(row["id"])),
        email=str(row["email"]),
        email_normalized=str(row["email_normalized"]),
        username=username,
        username_normalized=username_normalized,
        role=role,
        password_hash=str(row["password_hash"]),
        email_verified_at=_as_utc(row["email_verified_at"]),
        created_at=_as_utc(row["created_at"]) or datetime.now(UTC),
        updated_at=_as_utc(row["updated_at"]) or datetime.now(UTC),
    )


def _session_from_row(row: dict[str, Any]) -> SessionRecord:
    return SessionRecord(
        id_hash=str(row["id_hash"]),
        user_id=UserId(str(row["user_id"])),
        csrf_hash=str(row["csrf_hash"]),
        created_at=_as_utc(row["created_at"]) or datetime.now(UTC),
        expires_at=_as_utc(row["expires_at"]) or datetime.now(UTC),
        last_seen_at=_as_utc(row["last_seen_at"]) or datetime.now(UTC),
        revoked_at=_as_utc(row["revoked_at"]),
    )


def _token_from_row(row: dict[str, Any]) -> AuthTokenRecord:
    return AuthTokenRecord(
        id=str(row["id"]),
        user_id=UserId(str(row["user_id"])),
        purpose=AuthTokenPurpose(str(row["purpose"])),
        token_hash=str(row["token_hash"]),
        created_at=_as_utc(row["created_at"]) or datetime.now(UTC),
        expires_at=_as_utc(row["expires_at"]) or datetime.now(UTC),
        used_at=_as_utc(row["used_at"]),
    )
