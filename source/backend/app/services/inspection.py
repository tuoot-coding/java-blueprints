"""Общий шаг: лимит размера, разбор Tree-sitter и структурный IR."""

from __future__ import annotations

from dataclasses import dataclass

from app.ir.builder import build_structural_ir
from app.ir.models import IrNode
from app.parser.service import JavaInspection, inspect_java_source
from app.services.source_guard import ensure_java_source_size
from app.transform.fingerprint import source_fingerprint


@dataclass(frozen=True, slots=True)
class LoadedJava:
    source: str
    source_hash: str
    inspection: JavaInspection
    ir: IrNode


def load_java(source: str, *, max_source_bytes: int) -> LoadedJava:
    """Проверяет размер и строит IR из того же текста, который разобрал парсер."""
    ensure_java_source_size(source, max_source_bytes=max_source_bytes)
    inspection = inspect_java_source(source)
    return LoadedJava(
        source=source,
        source_hash=source_fingerprint(source),
        inspection=inspection,
        ir=build_structural_ir(source, inspection.tree),
    )
