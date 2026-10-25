"""Схемы POST /api/v1/fixes/apply."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.parser.models import JavaParseResult
from app.schemas.parser import (
    CoordinateSystemSchema,
    DiagnosticCodeSchema,
    DiagnosticSeveritySchema,
    ParseStatusSchema,
    SyntaxDiagnostic,
)
from app.transform.apply_fix import AppliedFix


class ApplyFixRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    fix_id: str = Field(min_length=1, max_length=200)
    expected_source_hash: str = Field(min_length=64, max_length=64)
    expected_start_byte: int = Field(ge=0)
    expected_end_byte: int = Field(ge=0)
    expected_text: str


class ApplyFixResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    source_hash: str
    fix_id: str
    status: ParseStatusSchema
    has_syntax_errors: bool
    diagnostics: list[SyntaxDiagnostic]
    coordinate_system: CoordinateSystemSchema = (
        CoordinateSystemSchema.LINE_UTF16_COLUMN_1_BASED_HALF_OPEN
    )

    @classmethod
    def from_applied(cls, applied: AppliedFix) -> ApplyFixResponse:
        result = applied.parse_result
        return cls(
            source=applied.source,
            source_hash=applied.source_hash,
            fix_id=applied.fix_id,
            status=ParseStatusSchema(result.status.value),
            has_syntax_errors=result.has_syntax_errors,
            diagnostics=_syntax_diagnostics(result),
        )


def _syntax_diagnostics(result: JavaParseResult) -> list[SyntaxDiagnostic]:
    return [
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
    ]
