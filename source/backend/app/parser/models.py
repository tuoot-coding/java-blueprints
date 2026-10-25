"""Внутренние модели результата разбора (не Pydantic API)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ParseStatus(StrEnum):
    """Статус синтаксического разбора Tree-sitter."""

    OK = "ok"
    SYNTAX_ERRORS = "syntax_errors"


class DiagnosticSeverity(StrEnum):
    ERROR = "error"


class DiagnosticCode(StrEnum):
    SYNTAX_ERROR = "java.syntax_error"
    MISSING_NODE = "java.missing_node"


@dataclass(frozen=True, slots=True)
class SourceDiagnostic:
    severity: DiagnosticSeverity
    code: DiagnosticCode
    message: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    start_byte: int
    end_byte: int


@dataclass(frozen=True, slots=True)
class SyntaxRootInfo:
    type: str
    start_byte: int
    end_byte: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    child_count: int


@dataclass(frozen=True, slots=True)
class JavaParseResult:
    """Структурированный результат parse_java_source."""

    status: ParseStatus
    has_syntax_errors: bool
    diagnostics: tuple[SourceDiagnostic, ...]
    root: SyntaxRootInfo
    source_byte_length: int
    # Исходная строка без изменений; для проверки round-trip без Storage.
    source: str
