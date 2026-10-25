"""Схемы POST /api/v1/analysis/analyze."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.engine import AnalysisRun
from app.analysis.models import AnalysisDiagnostic, MethodMetric
from app.schemas.parser import CoordinateSystemSchema
from app.schemas.span import SourceSpanSchema
from app.transform.quick_fixes import QuickFix


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(description="Исходный текст Java в UTF-8.")


class AnalysisDiagnosticSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    rule_id: str
    message: str
    explanation: str
    span: SourceSpanSchema
    related_ir_ids: list[str]
    quick_fix_id: str | None = None


class QuickFixSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    rule_id: str
    title: str
    start_byte: int = Field(ge=0)
    end_byte: int = Field(ge=0)
    replacement: str
    expected_text: str


class MethodMetricSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    method_name: str
    ir_node_id: str
    cyclomatic_complexity: int = Field(ge=1)
    cfg_partial: bool | None


class AnalysisMetricsSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    methods: list[MethodMetricSchema]
    max_cyclomatic_complexity: int = Field(ge=0)
    unsupported_count: int = Field(ge=0)


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    diagnostics: list[AnalysisDiagnosticSchema]
    quick_fixes: list[QuickFixSchema]
    metrics: AnalysisMetricsSchema
    coordinate_system: CoordinateSystemSchema = (
        CoordinateSystemSchema.LINE_UTF16_COLUMN_1_BASED_HALF_OPEN
    )
    source_hash: str
    has_syntax_errors: bool

    @classmethod
    def from_run(
        cls,
        run: AnalysisRun,
        *,
        source_hash: str,
        has_syntax_errors: bool,
    ) -> AnalyzeResponse:
        return cls(
            diagnostics=[_diagnostic_schema(item) for item in run.diagnostics],
            quick_fixes=[_fix_schema(item) for item in run.quick_fixes],
            metrics=AnalysisMetricsSchema(
                methods=[_metric_schema(item) for item in run.metrics.methods],
                max_cyclomatic_complexity=run.metrics.max_cyclomatic_complexity,
                unsupported_count=run.metrics.unsupported_count,
            ),
            source_hash=source_hash,
            has_syntax_errors=has_syntax_errors,
        )


def _diagnostic_schema(item: AnalysisDiagnostic) -> AnalysisDiagnosticSchema:
    return AnalysisDiagnosticSchema(
        severity=item.severity.value,
        rule_id=item.rule_id.value,
        message=item.message,
        explanation=item.explanation,
        span=SourceSpanSchema.from_span(item.span),
        related_ir_ids=list(item.related_ir_ids),
        quick_fix_id=item.quick_fix_id,
    )


def _fix_schema(item: QuickFix) -> QuickFixSchema:
    return QuickFixSchema(
        id=item.id,
        rule_id=item.rule_id,
        title=item.title,
        start_byte=item.start_byte,
        end_byte=item.end_byte,
        replacement=item.replacement,
        expected_text=item.expected_text,
    )


def _metric_schema(item: MethodMetric) -> MethodMetricSchema:
    return MethodMetricSchema(
        method_name=item.method_name,
        ir_node_id=item.ir_node_id,
        cyclomatic_complexity=item.cyclomatic_complexity,
        cfg_partial=item.cfg_partial,
    )
