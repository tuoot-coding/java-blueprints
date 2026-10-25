"""Сервис синтаксического разбора Java: parse_java_source."""

from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Parser, Tree

from app.parser.models import (
    DiagnosticCode,
    DiagnosticSeverity,
    JavaParseResult,
    ParseStatus,
    SourceDiagnostic,
    SyntaxRootInfo,
)
from app.parser.positions import byte_range_to_positions
from app.parser.tree_sitter_adapter import create_java_parser, parse_java_bytes
from app.texts.parser import get_parser_message

_PARSER: Parser | None = None


def _shared_parser() -> Parser:
    global _PARSER
    if _PARSER is None:
        _PARSER = create_java_parser()
    return _PARSER


@dataclass(frozen=True, slots=True)
class JavaInspection:
    """Результат разбора вместе с деревом Tree-sitter для внутренних проходов."""

    result: JavaParseResult
    tree: Tree


def parse_java_source(source: str) -> JavaParseResult:
    """Разбирает Java-исходник через tree-sitter-java.

    Не изменяет исходную строку. Не выполняет семантическую проверку javac.
    Некорректный синтаксис отражается в diagnostics и status=syntax_errors.
    """
    return inspect_java_source(source).result


def inspect_java_source(source: str) -> JavaInspection:
    """Разбирает Java один раз и возвращает диагностику вместе с деревом."""
    source_bytes = source.encode("utf-8")
    parsed = parse_java_bytes(source_bytes, parser=_shared_parser())
    root_node = parsed.tree.root_node

    start_line, start_column, end_line, end_column = byte_range_to_positions(
        source,
        source_bytes,
        root_node.start_byte,
        root_node.end_byte,
    )
    root = SyntaxRootInfo(
        type=root_node.type,
        start_byte=root_node.start_byte,
        end_byte=root_node.end_byte,
        start_line=start_line,
        start_column=start_column,
        end_line=end_line,
        end_column=end_column,
        child_count=root_node.child_count,
    )

    diagnostics: list[SourceDiagnostic] = []
    for problem in parsed.problems:
        code = (
            DiagnosticCode.MISSING_NODE
            if problem.kind == "missing"
            else DiagnosticCode.SYNTAX_ERROR
        )
        (
            diag_start_line,
            diag_start_column,
            diag_end_line,
            diag_end_column,
        ) = byte_range_to_positions(
            source,
            source_bytes,
            problem.start_byte,
            problem.end_byte,
        )
        # Пустой диапазон (missing без длины) расширяем до одной позиции для отображения.
        if (
            diag_start_line == diag_end_line
            and diag_start_column == diag_end_column
            and problem.start_byte == problem.end_byte
        ):
            diag_end_column = diag_start_column + 1

        diagnostics.append(
            SourceDiagnostic(
                severity=DiagnosticSeverity.ERROR,
                code=code,
                message=get_parser_message(code),
                start_line=diag_start_line,
                start_column=diag_start_column,
                end_line=diag_end_line,
                end_column=diag_end_column,
                start_byte=problem.start_byte,
                end_byte=problem.end_byte,
            )
        )

    has_syntax_errors = bool(diagnostics) or parsed.has_error
    status = ParseStatus.SYNTAX_ERRORS if has_syntax_errors else ParseStatus.OK
    result = JavaParseResult(
        status=status,
        has_syntax_errors=has_syntax_errors,
        diagnostics=tuple(diagnostics),
        root=root,
        source_byte_length=len(source_bytes),
        source=source,
    )
    return JavaInspection(result=result, tree=parsed.tree)
