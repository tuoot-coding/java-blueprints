"""Middleware контекста запроса и access-лога."""

from __future__ import annotations

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.error_handlers import build_internal_error_response
from app.api.request_context import REQUEST_ID_HEADER, resolve_request_id
from app.core.logging import request_id_context

logger = logging.getLogger("app.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Назначает request_id, логирует запрос и перехватывает необработанные исключения.

    Перехват здесь, а не в ServerErrorMiddleware Starlette, гарантирует, что ответ 500
    тоже содержит X-Request-ID и формат ErrorResponse. В лог попадают только метод,
    путь без query, статус и длительность: тело запроса может содержать исходник пользователя.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        context_token = request_id_context.set(request_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "unhandled_exception method=%s path=%s", request.method, request.url.path
                )
                response = build_internal_error_response(request_id)
            response.headers[REQUEST_ID_HEADER] = request_id
            logger.info(
                "http_request method=%s path=%s status=%d duration_ms=%.1f",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - started) * 1000,
            )
            return response
        finally:
            request_id_context.reset(context_token)
