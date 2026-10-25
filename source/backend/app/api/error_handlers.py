"""Централизованное преобразование исключений в ErrorResponse."""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.request_context import get_request_id
from app.core.errors import ApplicationError
from app.schemas.errors import ErrorCode, ErrorResponse, ValidationIssue
from app.texts.errors import get_error_message

_HTTP_STATUS_ERROR_CODES: Mapping[int, ErrorCode] = {
    HTTPStatus.BAD_REQUEST: ErrorCode.BAD_REQUEST,
    HTTPStatus.NOT_FOUND: ErrorCode.NOT_FOUND,
    HTTPStatus.METHOD_NOT_ALLOWED: ErrorCode.METHOD_NOT_ALLOWED,
    HTTPStatus.REQUEST_ENTITY_TOO_LARGE: ErrorCode.PAYLOAD_TOO_LARGE,
}


def build_error_response(
    *,
    status_code: int,
    error_code: ErrorCode,
    request_id: str,
    details: dict[str, Any] | None = None,
    validation_issues: list[ValidationIssue] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error_code=error_code,
        message=get_error_message(error_code),
        request_id=request_id,
        details=details,
        validation_issues=validation_issues,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=dict(headers) if headers else None,
    )


def build_internal_error_response(request_id: str) -> JSONResponse:
    """Ответ 500 никогда не содержит traceback и текст исключения, в том числе при DEBUG."""
    return build_error_response(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        error_code=ErrorCode.INTERNAL_ERROR,
        request_id=request_id,
    )


async def handle_application_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApplicationError)  # noqa: S101 - сужение типа для mypy
    return build_error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        request_id=get_request_id(request),
        details=exc.details,
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101 - сужение типа для mypy
    return build_error_response(
        status_code=exc.status_code,
        error_code=_HTTP_STATUS_ERROR_CODES.get(exc.status_code, ErrorCode.HTTP_ERROR),
        request_id=get_request_id(request),
        headers=exc.headers,
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Входные значения не возвращаются: в них может быть исходный код пользователя."""
    assert isinstance(exc, RequestValidationError)  # noqa: S101 - сужение типа для mypy
    issues = [
        ValidationIssue(
            location=list(error.get("loc", ())),
            message=str(error.get("msg", "")),
            type=str(error.get("type", "")),
        )
        for error in exc.errors()
    ]
    return build_error_response(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        error_code=ErrorCode.VALIDATION_ERROR,
        request_id=get_request_id(request),
        validation_issues=issues,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, handle_application_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
