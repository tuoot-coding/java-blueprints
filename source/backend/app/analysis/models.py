"""Диагностики статического анализа. Это не синтаксические ошибки парсера."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.ir.models import SourceSpan
from app.texts.analysis import AnalysisRule


class AnalysisSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


@dataclass(frozen=True, slots=True)
class AnalysisDiagnostic:
    severity: AnalysisSeverity
    rule_id: AnalysisRule
    message: str
    explanation: str
    span: SourceSpan
    related_ir_ids: tuple[str, ...]
    quick_fix_id: str | None = None


@dataclass(frozen=True, slots=True)
class MethodMetric:
    method_name: str
    ir_node_id: str
    cyclomatic_complexity: int
    cfg_partial: bool | None


@dataclass(frozen=True, slots=True)
class AnalysisMetrics:
    methods: tuple[MethodMetric, ...]
    max_cyclomatic_complexity: int
    unsupported_count: int
