"""Базовое исключение прикладного уровня с машинным кодом ошибки."""

from __future__ import annotations

from typing import Any

from app.schemas.errors import ErrorCode


class ApplicationError(Exception):
    """Ожидаемая ошибка продукта, которая отдается клиенту как ErrorResponse.

    Сообщение для клиента берется из словаря app.texts.errors по error_code,
    поэтому в исключение передаются только код, HTTP-статус и безопасные детали.
    """

    def __init__(
        self,
        error_code: ErrorCode,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(error_code.value)
        self.error_code = error_code
        self.status_code = status_code
        self.details = details
