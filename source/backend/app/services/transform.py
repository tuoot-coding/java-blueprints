"""Оркестрация структурной генерации Java."""

from __future__ import annotations

from app.services.source_guard import ensure_java_source_size
from app.transform.generate import generate_java_from_ir


def generate_java_request(source: str, *, max_source_bytes: int) -> tuple[str, str]:
    ensure_java_source_size(source, max_source_bytes=max_source_bytes)
    return generate_java_from_ir(source)
