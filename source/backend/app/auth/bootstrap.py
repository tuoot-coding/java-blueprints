"""Сборка AuthService и хранилища из Settings."""

from __future__ import annotations

from app.auth.cookies import AuthCookieSettings
from app.auth.email_sender import LoggingEmailSender, SmtpEmailSender
from app.auth.memory_store import MemoryAuthStore
from app.auth.mysql_store import MysqlAuthStore
from app.auth.service import AuthService, AuthSettings
from app.auth.store import AuthStore
from app.core.config import Settings


def build_auth_store(settings: Settings) -> AuthStore:
    if settings.auth_store == "memory":
        return MemoryAuthStore()
    assert settings.auth_mysql_dsn is not None
    return MysqlAuthStore(settings.auth_mysql_dsn)


def build_email_sender(settings: Settings) -> SmtpEmailSender | LoggingEmailSender:
    if settings.auth_store == "memory":
        # Тесты и локальный memory-режим: без SMTP, токены в лог не пишем.
        return LoggingEmailSender()
    return SmtpEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        from_address=settings.smtp_from,
        username=settings.smtp_username,
        password=settings.smtp_password,
        use_tls=settings.smtp_use_tls,
    )


def build_auth_service(settings: Settings, store: AuthStore | None = None) -> AuthService:
    auth_store = store or build_auth_store(settings)
    email_sender = build_email_sender(settings)
    auth_settings = AuthSettings(
        password_min_length=settings.auth_password_min_length,
        enforce_password_complexity=settings.auth_enforce_password_complexity,
        hibp_enabled=settings.auth_hibp_enabled,
        hibp_timeout_seconds=settings.auth_hibp_timeout_seconds,
        session_ttl_seconds=settings.auth_session_ttl_seconds,
        email_verify_ttl_seconds=settings.auth_email_verify_ttl_seconds,
        password_reset_ttl_seconds=settings.auth_password_reset_ttl_seconds,
        login_rate_max=settings.auth_login_rate_max,
        login_rate_window_seconds=settings.auth_login_rate_window_seconds,
        reset_rate_max=settings.auth_reset_rate_max,
        reset_rate_window_seconds=settings.auth_reset_rate_window_seconds,
        public_app_base_url=settings.public_app_base_url,
        cookie=AuthCookieSettings(
            session_cookie_name=settings.auth_cookie_name,
            csrf_cookie_name=settings.auth_csrf_cookie_name,
            secure=settings.auth_cookie_secure,
            samesite=settings.auth_cookie_samesite,
            max_age_seconds=settings.auth_session_ttl_seconds,
        ),
        dev_auto_verify_email=settings.auth_dev_auto_verify_email,
    )
    return AuthService(auth_store, email_sender, auth_settings)
