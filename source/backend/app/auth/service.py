"""Бизнес-логика регистрации, входа, сессий и сброса пароля."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from app.auth.cookies import AuthCookieSettings
from app.auth.email_sender import (
    EmailSender,
    build_password_reset_email,
    build_verify_email,
)
from app.auth.hibp import password_is_pwned
from app.auth.models import AuthTokenPurpose, SessionRecord, UserRecord, UserRole
from app.auth.passwords import (
    hash_password,
    needs_rehash,
    validate_password_policy,
    verify_password,
)
from app.auth.rate_limit import assert_not_rate_limited, clear_auth_failures, register_auth_failure
from app.auth.store import AuthStore
from app.auth.tokens import generate_opaque_token, hash_opaque_token
from app.core.errors import ApplicationError
from app.schemas.errors import ErrorCode

logger = logging.getLogger("app.auth")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,31}$")


@dataclass(frozen=True, slots=True)
class AuthSettings:
    password_min_length: int
    enforce_password_complexity: bool
    hibp_enabled: bool
    hibp_timeout_seconds: float
    session_ttl_seconds: int
    email_verify_ttl_seconds: int
    password_reset_ttl_seconds: int
    login_rate_max: int
    login_rate_window_seconds: int
    reset_rate_max: int
    reset_rate_window_seconds: int
    public_app_base_url: str
    cookie: AuthCookieSettings
    # Временно для разработки: сразу подтверждать email без письма.
    dev_auto_verify_email: bool


@dataclass(frozen=True, slots=True)
class IssuedSession:
    session_token: str
    csrf_token: str
    user: UserRecord
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuthSessionContext:
    user: UserRecord
    session: SessionRecord
    session_token: str
    csrf_token_cookie: str | None


class AuthService:
    def __init__(
        self,
        store: AuthStore,
        email_sender: EmailSender,
        settings: AuthSettings,
    ) -> None:
        self._store = store
        self._email = email_sender
        self._settings = settings

    @property
    def cookie_settings(self) -> AuthCookieSettings:
        return self._settings.cookie

    def register(
        self,
        *,
        email: str,
        username: str,
        password: str,
        role: UserRole,
        client_key: str,
    ) -> None:
        """Анти-enumeration по email; занятый username возвращает явную ошибку."""
        assert_not_rate_limited(self._store, f"register:{client_key}")
        normalized = normalize_email(email)
        username_clean, username_normalized = normalize_username(username)
        self._validate_password(password)

        by_username = self._store.get_user_by_username_normalized(username_normalized)
        existing = self._store.get_user_by_email_normalized(normalized)
        if by_username is not None and (existing is None or by_username.id != existing.id):
            raise ApplicationError(ErrorCode.AUTH_USERNAME_TAKEN, status_code=409)

        if existing is None:
            user = self._store.create_user(
                email=email.strip(),
                email_normalized=normalized,
                username=username_clean,
                username_normalized=username_normalized,
                role=role,
                password_hash=hash_password(password),
            )
            if self._settings.dev_auto_verify_email:
                self._store.mark_email_verified(user.id, datetime.now(UTC))
                logger.info("auth_register_created_auto_verified user_id=%s", user.id)
            else:
                self._issue_and_send_verify(user)
                logger.info("auth_register_created user_id=%s", user.id)
            return

        if existing.is_email_verified:
            logger.info("auth_register_existing_verified")
            return

        self._store.update_password_hash(existing.id, hash_password(password))
        self._store.update_role(existing.id, role)
        if self._settings.dev_auto_verify_email:
            self._store.mark_email_verified(existing.id, datetime.now(UTC))
            logger.info("auth_register_existing_auto_verified user_id=%s", existing.id)
        else:
            self._issue_and_send_verify(existing)
            logger.info("auth_register_resent_verification user_id=%s", existing.id)

    def change_password(
        self, *, user: UserRecord, current_password: str, new_password: str
    ) -> IssuedSession:
        if not verify_password(user.password_hash, current_password):
            raise ApplicationError(ErrorCode.AUTH_INVALID_CREDENTIALS, status_code=401)
        self._validate_password(new_password)
        self._store.update_password_hash(user.id, hash_password(new_password))
        # Отзываем все сессии и выдаём новую текущему клиенту.
        refreshed = self._store.get_user_by_id(user.id)
        assert refreshed is not None
        issued = self._create_session(refreshed)
        logger.info("auth_password_changed user_id=%s", user.id)
        return issued

    def update_role(self, *, user: UserRecord, role: UserRole) -> UserRecord:
        """Временная смена роли на этапе разработки."""
        self._store.update_role(user.id, role)
        updated = self._store.get_user_by_id(user.id)
        assert updated is not None
        logger.info("auth_role_updated user_id=%s role=%s", user.id, role.value)
        return updated

    def login(self, *, email: str, password: str, client_key: str) -> IssuedSession:
        bucket = f"login:{client_key}"
        assert_not_rate_limited(self._store, bucket)
        normalized = normalize_email(email)
        user = self._store.get_user_by_email_normalized(normalized)
        if user is None or not verify_password(user.password_hash, password):
            register_auth_failure(
                self._store,
                bucket,
                max_failures=self._settings.login_rate_max,
                window_seconds=self._settings.login_rate_window_seconds,
            )
            logger.info("auth_login_failed reason=invalid_credentials")
            raise ApplicationError(ErrorCode.AUTH_INVALID_CREDENTIALS, status_code=401)

        if not user.is_email_verified:
            register_auth_failure(
                self._store,
                bucket,
                max_failures=self._settings.login_rate_max,
                window_seconds=self._settings.login_rate_window_seconds,
            )
            logger.info("auth_login_failed reason=email_not_verified user_id=%s", user.id)
            raise ApplicationError(ErrorCode.AUTH_EMAIL_NOT_VERIFIED, status_code=403)

        if needs_rehash(user.password_hash):
            self._store.update_password_hash(user.id, hash_password(password))

        clear_auth_failures(self._store, bucket)
        issued = self._create_session(user)
        logger.info("auth_login_success user_id=%s", user.id)
        return issued

    def logout(self, *, session_token: str | None) -> None:
        if not session_token:
            return
        session = self._store.get_session_by_hash(hash_opaque_token(session_token))
        if session is None or not session.is_active:
            return
        self._store.revoke_session(session.id_hash, revoked_at=datetime.now(UTC))
        logger.info("auth_logout user_id=%s", session.user_id)

    def resolve_session(self, *, session_token: str | None) -> AuthSessionContext | None:
        if not session_token:
            return None
        now = datetime.now(UTC)
        session = self._store.get_session_by_hash(hash_opaque_token(session_token))
        if session is None or not session.is_active or session.expires_at <= now:
            return None
        user = self._store.get_user_by_id(session.user_id)
        if user is None or not user.is_email_verified:
            return None
        new_expires = now + timedelta(seconds=self._settings.session_ttl_seconds)
        self._store.touch_session(session.id_hash, last_seen_at=now, expires_at=new_expires)
        refreshed = self._store.get_session_by_hash(session.id_hash) or session
        return AuthSessionContext(
            user=user,
            session=refreshed,
            session_token=session_token,
            csrf_token_cookie=None,
        )

    def verify_csrf(
        self,
        *,
        session: SessionRecord,
        csrf_header: str | None,
        csrf_cookie: str | None,
    ) -> None:
        if not csrf_header or not csrf_cookie:
            raise ApplicationError(ErrorCode.AUTH_CSRF_FAILED, status_code=403)
        if not constant_time_token_equals(csrf_header, csrf_cookie):
            raise ApplicationError(ErrorCode.AUTH_CSRF_FAILED, status_code=403)
        if hash_opaque_token(csrf_header) != session.csrf_hash:
            raise ApplicationError(ErrorCode.AUTH_CSRF_FAILED, status_code=403)

    def verify_email(self, *, token: str) -> None:
        record = self._store.get_auth_token_by_hash(
            hash_opaque_token(token),
            purpose=AuthTokenPurpose.EMAIL_VERIFY,
        )
        now = datetime.now(UTC)
        if record is None or record.used_at is not None or record.expires_at <= now:
            raise ApplicationError(ErrorCode.AUTH_TOKEN_INVALID, status_code=400)
        self._store.mark_auth_token_used(record.id, used_at=now)
        self._store.mark_email_verified(record.user_id, now)
        self._store.invalidate_auth_tokens(
            record.user_id, purpose=AuthTokenPurpose.EMAIL_VERIFY, at=now
        )
        logger.info("auth_email_verified user_id=%s", record.user_id)

    def resend_verification(self, *, email: str, client_key: str) -> None:
        """Анти-enumeration: ответ снаружи одинаковый."""
        assert_not_rate_limited(self._store, f"resend:{client_key}")
        register_auth_failure(
            self._store,
            f"resend:{client_key}",
            max_failures=self._settings.reset_rate_max,
            window_seconds=self._settings.reset_rate_window_seconds,
        )
        normalized = normalize_email(email)
        user = self._store.get_user_by_email_normalized(normalized)
        if user is None or user.is_email_verified:
            logger.info("auth_verification_resent result=noop")
            return
        self._issue_and_send_verify(user)
        logger.info("auth_verification_resent user_id=%s", user.id)

    def request_password_reset(self, *, email: str, client_key: str) -> None:
        """Анти-enumeration: всегда одно и то же поведение снаружи."""
        bucket = f"reset:{client_key}"
        assert_not_rate_limited(self._store, bucket)
        register_auth_failure(
            self._store,
            bucket,
            max_failures=self._settings.reset_rate_max,
            window_seconds=self._settings.reset_rate_window_seconds,
        )
        normalized = normalize_email(email)
        user = self._store.get_user_by_email_normalized(normalized)
        if user is None:
            logger.info("auth_password_reset_requested result=unknown_email")
            return
        now = datetime.now(UTC)
        self._store.invalidate_auth_tokens(
            user.id, purpose=AuthTokenPurpose.PASSWORD_RESET, at=now
        )
        raw = generate_opaque_token()
        self._store.create_auth_token(
            token_id=uuid.uuid4().hex,
            user_id=user.id,
            purpose=AuthTokenPurpose.PASSWORD_RESET,
            token_hash=hash_opaque_token(raw),
            created_at=now,
            expires_at=now + timedelta(seconds=self._settings.password_reset_ttl_seconds),
        )
        reset_url = self._app_url("/auth/password-reset/confirm", {"token": raw})
        try:
            self._email.send(build_password_reset_email(user.email, reset_url=reset_url))
        except OSError:
            logger.warning("auth_password_reset_email_failed user_id=%s", user.id)
        logger.info("auth_password_reset_requested result=sent user_id=%s", user.id)

    def confirm_password_reset(self, *, token: str, new_password: str, client_key: str) -> None:
        bucket = f"reset-confirm:{client_key}"
        assert_not_rate_limited(self._store, bucket)
        self._validate_password(new_password)
        record = self._store.get_auth_token_by_hash(
            hash_opaque_token(token),
            purpose=AuthTokenPurpose.PASSWORD_RESET,
        )
        now = datetime.now(UTC)
        if record is None or record.used_at is not None or record.expires_at <= now:
            register_auth_failure(
                self._store,
                bucket,
                max_failures=self._settings.reset_rate_max,
                window_seconds=self._settings.reset_rate_window_seconds,
            )
            raise ApplicationError(ErrorCode.AUTH_TOKEN_INVALID, status_code=400)

        self._store.mark_auth_token_used(record.id, used_at=now)
        self._store.invalidate_auth_tokens(
            record.user_id, purpose=AuthTokenPurpose.PASSWORD_RESET, at=now
        )
        self._store.update_password_hash(record.user_id, hash_password(new_password))
        self._store.revoke_user_sessions(record.user_id, revoked_at=now)
        clear_auth_failures(self._store, bucket)
        logger.info("auth_password_reset_confirmed user_id=%s", record.user_id)

    def _validate_password(self, password: str) -> None:
        validate_password_policy(
            password,
            min_length=self._settings.password_min_length,
            enforce_complexity=self._settings.enforce_password_complexity,
        )
        self._reject_pwned_password(password)

    def _reject_pwned_password(self, password: str) -> None:
        if password_is_pwned(
            password,
            enabled=self._settings.hibp_enabled,
            timeout_seconds=self._settings.hibp_timeout_seconds,
            fail_open=True,
        ):
            raise ApplicationError(ErrorCode.AUTH_PASSWORD_PWNED, status_code=422)

    def _issue_and_send_verify(self, user: UserRecord) -> None:
        now = datetime.now(UTC)
        self._store.invalidate_auth_tokens(
            user.id, purpose=AuthTokenPurpose.EMAIL_VERIFY, at=now
        )
        raw = generate_opaque_token()
        self._store.create_auth_token(
            token_id=uuid.uuid4().hex,
            user_id=user.id,
            purpose=AuthTokenPurpose.EMAIL_VERIFY,
            token_hash=hash_opaque_token(raw),
            created_at=now,
            expires_at=now + timedelta(seconds=self._settings.email_verify_ttl_seconds),
        )
        verify_url = self._app_url("/auth/verify-email", {"token": raw})
        try:
            self._email.send(build_verify_email(user.email, verify_url=verify_url))
        except OSError:
            logger.warning("auth_verify_email_failed user_id=%s", user.id)

    def _create_session(self, user: UserRecord) -> IssuedSession:
        now = datetime.now(UTC)
        # Ротация: все предыдущие сессии пользователя отзываются при новом входе.
        self._store.revoke_user_sessions(user.id, revoked_at=now)
        session_token = generate_opaque_token()
        csrf_token = generate_opaque_token(nbytes=24)
        expires_at = now + timedelta(seconds=self._settings.session_ttl_seconds)
        self._store.create_session(
            id_hash=hash_opaque_token(session_token),
            user_id=user.id,
            csrf_hash=hash_opaque_token(csrf_token),
            created_at=now,
            expires_at=expires_at,
        )
        return IssuedSession(
            session_token=session_token,
            csrf_token=csrf_token,
            user=user,
            expires_at=expires_at,
        )

    def _app_url(self, path: str, query: dict[str, str]) -> str:
        base = self._settings.public_app_base_url.rstrip("/")
        return f"{base}{path}?{urlencode(query)}"


def normalize_email(email: str) -> str:
    cleaned = email.strip().lower()
    if not cleaned or len(cleaned) > 320 or not _EMAIL_RE.match(cleaned):
        raise ApplicationError(ErrorCode.VALIDATION_ERROR, status_code=422)
    return cleaned


def normalize_username(username: str) -> tuple[str, str]:
    cleaned = username.strip()
    if not _USERNAME_RE.match(cleaned):
        raise ApplicationError(ErrorCode.AUTH_USERNAME_INVALID, status_code=422)
    return cleaned, cleaned.lower()


def constant_time_token_equals(left: str, right: str) -> bool:
    from app.auth.tokens import constant_time_equals

    return constant_time_equals(left, right)


def client_rate_key(*, ip: str | None, email: str | None = None) -> str:
    parts = [(ip or "unknown").strip()[:64]]
    if email:
        parts.append(email.strip().lower()[:128])
    return "|".join(parts)
