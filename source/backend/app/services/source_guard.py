"""Общая проверка лимита размера Java-исходника для HTTP-операций."""

from __future__ import annotations

from http import HTTPStatus

from app.core.errors import ApplicationError
from app.schemas.errors import ErrorCode


def ensure_java_source_size(source: str, *, max_source_bytes: int) -> None:
    """Отклоняет исходник, который не помещается в лимит UTF-8 байтов."""
    actual_source_bytes = len(source.encode("utf-8"))
    if actual_source_bytes > max_source_bytes:
        raise ApplicationError(
            ErrorCode.PAYLOAD_TOO_LARGE,
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            details={
                "max_source_bytes": max_source_bytes,
                "actual_source_bytes": actual_source_bytes,
            },
        )
