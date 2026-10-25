"""Зависимости FastAPI для доступа к состоянию приложения."""

from __future__ import annotations

from fastapi import Request

from app.auth.models import UserRecord
from app.auth.service import AuthService
from app.core.config import Settings
from app.core.errors import ApplicationError
from app.schemas.errors import ErrorCode
from app.services.health import ApplicationRuntime


def get_application_runtime(request: Request) -> ApplicationRuntime:
    runtime = request.app.state.runtime
    if not isinstance(runtime, ApplicationRuntime):
        raise RuntimeError("ApplicationRuntime не инициализирован в app.state")
    return runtime


def get_settings_dependency(request: Request) -> Settings:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("Settings не инициализированы в app.state")
    return settings


def get_auth_service(request: Request) -> AuthService:
    auth = request.app.state.auth_service
    if not isinstance(auth, AuthService):
        raise RuntimeError("AuthService не инициализирован в app.state")
    return auth


def get_current_user(request: Request) -> UserRecord:
    user = getattr(request.state, "auth_user", None)
    if not isinstance(user, UserRecord):
        raise ApplicationError(ErrorCode.AUTH_REQUIRED, status_code=401)
    return user


def get_client_ip(request: Request) -> str | None:
    # Не доверяем X-Forwarded-For без reverse-proxy конфига; берём peer.
    if request.client is None:
        return None
    return request.client.host
