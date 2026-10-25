"""Оркестрация разбора Java для HTTP-слоя."""

from __future__ import annotations

from app.parser.models import JavaParseResult
from app.parser.service import parse_java_source
from app.services.source_guard import ensure_java_source_size


def parse_java_source_request(source: str, *, max_source_bytes: int) -> JavaParseResult:
    """Проверяет лимит размера и вызывает parse_java_source.

    Этот маршрут не пишет ревизию в Storage: исходник остается только в ответе разбора.
    """
    ensure_java_source_size(source, max_source_bytes=max_source_bytes)
    return parse_java_source(source)
