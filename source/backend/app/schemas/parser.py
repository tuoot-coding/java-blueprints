"""Pydantic-схемы Parser API."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.parser.models import JavaParseResult


class ParseStatusSchema(StrEnum):
    OK = "ok"
    SYNTAX_ERRORS = "syntax_errors"


class DiagnosticSeveritySchema(StrEnum):
    ERROR = "error"


class DiagnosticCodeSchema(StrEnum):
    SYNTAX_ERROR = "java.syntax_error"
    MISSING_NODE = "java.missing_node"


class CoordinateSystemSchema(StrEnum):
    """Система координат diagnostics и root.

    Строки и столбцы начинаются с 1. Столбцы измеряются в UTF-16 code units
    (как в Monaco Editor). Конечная позиция полуоткрытого диапазона [start, end).
    """

    LINE_UTF16_COLUMN_1_BASED_HALF_OPEN = "line_utf16_column_1_based_half_open"


class ParseJavaRequest(BaseModel):
    """Тело POST /api/v1/parser/parse."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(description="Исходный текст Java в UTF-8.")


class SyntaxDiagnostic(BaseModel):
    """Одна синтаксическая диагностика Parser."""

    model_config = ConfigDict(frozen=True)

    severity: DiagnosticSeveritySchema
    code: DiagnosticCodeSchema
    message: str
    start_line: int = Field(ge=1, description="Начальная строка, с 1.")
    start_column: int = Field(ge=1, description="Начальный столбец UTF-16, с 1.")
    end_line: int = Field(ge=1, description="Конечная строка, с 1 (exclusive end).")
    end_column: int = Field(ge=1, description="Конечный столбец UTF-16, с 1 (exclusive end).")
    start_byte: int = Field(ge=0, description="Начальное байтовое смещение UTF-8.")
    end_byte: int = Field(ge=0, description="Конечное байтовое смещение UTF-8 (exclusive).")


class SyntaxRootSummary(BaseModel):
    """Краткая информация о корневом узле синтаксического дерева."""

    model_config = ConfigDict(frozen=True)

    type: str
    start_byte: int = Field(ge=0)
    end_byte: int = Field(ge=0)
    start_line: int = Field(ge=1)
    start_column: int = Field(ge=1)
    end_line: int = Field(ge=1)
    end_column: int = Field(ge=1)
    child_count: int = Field(ge=0)


class ParseJavaResponse(BaseModel):
    """Ответ синтаксического разбора. HTTP 200 при корректном запросе, даже с ошибками Java."""

    model_config = ConfigDict(frozen=True)

    status: ParseStatusSchema
    has_syntax_errors: bool
    diagnostics: list[SyntaxDiagnostic]
    root: SyntaxRootSummary
    source_byte_length: int = Field(ge=0, description="Длина исходника в байтах UTF-8.")
    coordinate_system: CoordinateSystemSchema = (
        CoordinateSystemSchema.LINE_UTF16_COLUMN_1_BASED_HALF_OPEN
    )
    grammar: str = Field(default="tree-sitter-java", description="Использованная грамматика.")

    @classmethod
    def from_result(cls, result: JavaParseResult) -> ParseJavaResponse:
        return cls(
            status=ParseStatusSchema(result.status.value),
            has_syntax_errors=result.has_syntax_errors,
            diagnostics=[
                SyntaxDiagnostic(
                    severity=DiagnosticSeveritySchema(item.severity.value),
                    code=DiagnosticCodeSchema(item.code.value),
                    message=item.message,
                    start_line=item.start_line,
                    start_column=item.start_column,
                    end_line=item.end_line,
                    end_column=item.end_column,
                    start_byte=item.start_byte,
                    end_byte=item.end_byte,
                )
                for item in result.diagnostics
            ],
            root=SyntaxRootSummary(
                type=result.root.type,
                start_byte=result.root.start_byte,
                end_byte=result.root.end_byte,
                start_line=result.root.start_line,
                start_column=result.root.start_column,
                end_line=result.root.end_line,
                end_column=result.root.end_column,
                child_count=result.root.child_count,
            ),
            source_byte_length=result.source_byte_length,
        )
