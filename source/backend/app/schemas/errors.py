"""Единый формат ошибок HTTP API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    """Машинные коды ошибок, на которые опирается Frontend."""

    BAD_REQUEST = "bad_request"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    VALIDATION_ERROR = "validation_error"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    REVISION_CONFLICT = "revision_conflict"
    FIX_NOT_APPLICABLE = "fix_not_applicable"
    GENERATION_REFUSED = "generation_refused"
    LLM_UNAVAILABLE = "llm_unavailable"
    LLM_PAYMENT_REQUIRED = "llm_payment_required"
    LLM_TIMEOUT = "llm_timeout"
    HTTP_ERROR = "http_error"
    INTERNAL_ERROR = "internal_error"
    AUTH_REQUIRED = "auth_required"
    AUTH_INVALID_CREDENTIALS = "auth_invalid_credentials"
    AUTH_EMAIL_NOT_VERIFIED = "auth_email_not_verified"
    AUTH_CSRF_FAILED = "auth_csrf_failed"
    AUTH_RATE_LIMITED = "auth_rate_limited"
    AUTH_TOKEN_INVALID = "auth_token_invalid"
    AUTH_PASSWORD_POLICY = "auth_password_policy"
    AUTH_PASSWORD_PWNED = "auth_password_pwned"
    AUTH_USERNAME_TAKEN = "auth_username_taken"
    AUTH_USERNAME_INVALID = "auth_username_invalid"


class ValidationIssue(BaseModel):
    """Одна ошибка валидации запроса без эха входного значения."""

    model_config = ConfigDict(frozen=True)

    location: list[str | int] = Field(description="Путь к полю запроса.")
    message: str
    type: str = Field(description="Тип ошибки валидации Pydantic.")


class ErrorResponse(BaseModel):
    """Тело ответа любой ошибки API."""

    model_config = ConfigDict(frozen=True)

    error_code: ErrorCode
    message: str = Field(description="Сообщение для пользователя.")
    request_id: str = Field(description="Идентификатор запроса из заголовка X-Request-ID.")
    details: dict[str, Any] | None = None
    validation_issues: list[ValidationIssue] | None = None
