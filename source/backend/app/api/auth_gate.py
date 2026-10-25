"""Защита /api/v1: публичные health/auth, остальное - только с валидной сессией."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.error_handlers import build_error_response
from app.api.request_context import get_request_id
from app.auth.service import AuthService
from app.core.errors import ApplicationError
from app.core.metadata import API_V1_PREFIX
from app.schemas.errors import ErrorCode

CSRF_HEADER = "X-CSRF-Token"

_PUBLIC_EXACT = {
    f"{API_V1_PREFIX}/health",
    f"{API_V1_PREFIX}/openapi.json",
    f"{API_V1_PREFIX}/docs",
    f"{API_V1_PREFIX}/redoc",
    f"{API_V1_PREFIX}/auth/register",
    f"{API_V1_PREFIX}/auth/login",
    f"{API_V1_PREFIX}/auth/verify-email",
    f"{API_V1_PREFIX}/auth/resend-verification",
    f"{API_V1_PREFIX}/auth/password-reset/request",
    f"{API_V1_PREFIX}/auth/password-reset/confirm",
}

_PUBLIC_PREFIXES = (
    f"{API_V1_PREFIX}/docs",
    f"{API_V1_PREFIX}/redoc",
)

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def is_public_path(path: str) -> bool:
    if path in _PUBLIC_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)


class AuthGateMiddleware(BaseHTTPMiddleware):
    """Проверяет сессию и CSRF для защищённых маршрутов."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if not path.startswith(API_V1_PREFIX):
            return await call_next(request)
        if is_public_path(path):
            return await call_next(request)

        # Временный режим разработки: LLM / схема->код / parse без обязательного входа.
        settings = getattr(request.app.state, "settings", None)
        if settings is not None and not getattr(settings, "auth_api_gate_enabled", True):
            return await call_next(request)

        auth: AuthService = request.app.state.auth_service
        cookie_name = auth.cookie_settings.session_cookie_name
        csrf_cookie_name = auth.cookie_settings.csrf_cookie_name
        session_token = request.cookies.get(cookie_name)
        context = auth.resolve_session(session_token=session_token)
        if context is None:
            return build_error_response(
                status_code=HTTPStatus.UNAUTHORIZED,
                error_code=ErrorCode.AUTH_REQUIRED,
                request_id=get_request_id(request),
            )

        if request.method in _UNSAFE_METHODS:
            try:
                auth.verify_csrf(
                    session=context.session,
                    csrf_header=request.headers.get(CSRF_HEADER),
                    csrf_cookie=request.cookies.get(csrf_cookie_name),
                )
            except ApplicationError as exc:
                return build_error_response(
                    status_code=exc.status_code,
                    error_code=exc.error_code,
                    request_id=get_request_id(request),
                    details=exc.details,
                )

        request.state.auth_user = context.user
        request.state.auth_session = context.session
        return await call_next(request)
