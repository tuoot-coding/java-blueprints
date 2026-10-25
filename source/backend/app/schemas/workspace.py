"""Схемы workspace inspect и apply logic fix."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.ir.query import summarize_ir
from app.schemas.analysis import (
    AnalysisDiagnosticSchema,
    AnalysisMetricsSchema,
    QuickFixSchema,
    _diagnostic_schema,
    _fix_schema,
    _metric_schema,
)
from app.schemas.parser import CoordinateSystemSchema, ParseJavaResponse
from app.schemas.span import SourceSpanSchema
from app.schemas.structure import IrSummarySchema, StructuralBlockSchema


class WorkspaceInspectRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(description="Исходный текст Java в UTF-8.")
    include_llm: bool = Field(
        default=True,
        description="Запрашивать логический анализ через LLM, если ключ настроен.",
    )


class LlmSuggestedFixSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    replacement: str
    start_line: int = Field(ge=1)
    start_column: int = Field(ge=1)
    end_line: int = Field(ge=1)
    end_column: int = Field(ge=1)
    start_byte: int = Field(ge=0)
    end_byte: int = Field(ge=0)
    expected_snippet: str
    auto_applicable: bool


class LlmIssueSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    severity: str
    code: str
    title: str
    message: str
    explanation: str
    start_line: int = Field(ge=1)
    start_column: int = Field(ge=1)
    end_line: int = Field(ge=1)
    end_column: int = Field(ge=1)
    start_byte: int = Field(ge=0)
    end_byte: int = Field(ge=0)
    confidence: str
    fix: LlmSuggestedFixSchema | None = None
    affects_execution: bool = True


class BehaviorTestCaseSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    stdin: str
    expected_stdout: str
    expected_exit_code: int
    main_class_hint: str | None = None
    purpose: str = "workability"
    related_issue_id: str | None = None
    expects_original_failure: bool = False
    description: str = ""
    error_description: str = ""


class BehaviorTestRunSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    test_id: str
    name: str
    original_status: str
    generated_status: str
    original_exit_code: int | None
    generated_exit_code: int | None
    original_stdout: str
    generated_stdout: str
    expected_stdout: str
    matched_expected_original: bool
    matched_expected_generated: bool
    detail: str
    purpose: str = "workability"
    related_issue_id: str | None = None
    expects_original_failure: bool = False
    description: str = ""
    error_description: str = ""
    original_stderr: str = ""
    generated_stderr: str = ""
    original_wall_ms: int | None = None
    original_cpu_user_ms: int | None = None
    original_cpu_sys_ms: int | None = None
    original_max_rss_kb: int | None = None
    generated_wall_ms: int | None = None
    generated_cpu_user_ms: int | None = None
    generated_cpu_sys_ms: int | None = None
    generated_max_rss_kb: int | None = None
    wall_ratio: float | None = None
    cpu_ratio: float | None = None
    rss_ratio: float | None = None
    resources_vs_baseline: str = "n/a"


class BehaviorCompareSchema(BaseModel):
    """Сравнение двух версий по 10 LLM-тестам и метрикам."""

    model_config = ConfigDict(frozen=True)

    execution_available: bool
    execution_reason: str | None = None
    tests: list[BehaviorTestCaseSchema]
    runs: list[BehaviorTestRunSchema]
    original_passed: int
    generated_passed: int
    regressions: int
    improvements: int
    score: float
    passed: bool
    report_lines: list[str]
    notes: list[str] = Field(default_factory=list)


class LlmLogicalReviewSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    issues: list[LlmIssueSchema]
    notes: list[str]
    model: str | None
    error_reason: str | None = None


class ScratchLinkSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    target_id: str


class ScratchBlockSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    label: str
    ir_node_id: str
    span: SourceSpanSchema
    parent_id: str | None
    nest_level: int = Field(ge=0)
    color: str
    links: list[ScratchLinkSchema]
    source_snippet: str = ""
    module_id: str | None = None
    editable: bool = True


class ScratchModuleSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    name: str
    parent_module_id: str | None = None
    root_block_id: str
    block_ids: list[str]


class ScratchProgramSchema(BaseModel):
    """Модульная логическая блок-схема (ISO 5807 / ГОСТ 19.701)."""

    model_config = ConfigDict(frozen=True)

    method_name: str | None
    method_ir_id: str | None
    blocks: list[ScratchBlockSchema]
    root_block_ids: list[str]
    modules: list[ScratchModuleSchema] = Field(default_factory=list)
    method_names: list[str] = Field(default_factory=list)


class CodeCompareMetricsSchema(BaseModel):
    """Сравнительные метрики исходного и сгенерированного Java."""

    model_config = ConfigDict(frozen=True)

    elapsed_ms: float
    original_parse_ok: bool
    generated_parse_ok: bool
    class_names_match: bool
    public_methods_preserved: bool
    method_count_original: int
    method_count_generated: int
    method_count_delta: int
    line_count_original: int
    line_count_generated: int
    line_ratio: float
    max_method_lines_original: int
    max_method_lines_generated: int
    long_method_issues_original: int
    long_method_issues_generated: int
    duplicate_logic_original: int
    duplicate_logic_generated: int
    max_cyclomatic_original: int
    max_cyclomatic_generated: int
    source_changed: bool
    unsupported_original: int
    unsupported_generated: int
    score: float
    passed: bool
    report_lines: list[str]


class SchemeCompareSchema(BaseModel):
    """Сравнение исходной и новой модульной логической схемы."""

    model_config = ConfigDict(frozen=True)

    original_block_count: int
    generated_block_count: int
    original_module_count: int
    generated_module_count: int
    original_method_names: list[str]
    generated_method_names: list[str]
    methods_added: list[str]
    methods_removed: list[str]
    kinds_original: dict[str, int]
    kinds_generated: dict[str, int]
    kinds_delta: dict[str, int]
    structural_similarity: float
    outline_original: str
    outline_generated: str
    changed: bool
    report_lines: list[str]


class WorkspaceInspectResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    parse: ParseJavaResponse
    scratch: ScratchProgramSchema
    blocks: list[StructuralBlockSchema]
    ir_summary: IrSummarySchema
    static_diagnostics: list[AnalysisDiagnosticSchema]
    quick_fixes: list[QuickFixSchema]
    metrics: AnalysisMetricsSchema
    llm_configured: bool
    logical_review: LlmLogicalReviewSchema | None
    logical_error_count: int = Field(ge=0)
    coordinate_system: CoordinateSystemSchema = (
        CoordinateSystemSchema.LINE_UTF16_COLUMN_1_BASED_HALF_OPEN
    )
    source_hash: str

    @classmethod
    def from_result(cls, result: object) -> WorkspaceInspectResponse:
        from app.services.workspace import WorkspaceInspectResult

        if not isinstance(result, WorkspaceInspectResult):
            raise TypeError("ожидался WorkspaceInspectResult")
        analysis = result.analysis
        summary = summarize_ir(result.loaded.ir)
        logical = None
        logical_error_count = 0
        if result.logical_review is not None:
            review = result.logical_review
            # Считаем ошибками только влияющие на выполнение программы.
            logical_error_count = sum(
                1 for issue in review.issues if getattr(issue, "affects_execution", True)
            )
            logical = LlmLogicalReviewSchema(
                status=review.status,
                issues=[_issue_schema(issue) for issue in review.issues],
                notes=list(review.notes),
                model=review.model,
                error_reason=review.error_reason,
            )
        scratch = result.scratch
        return cls(
            parse=ParseJavaResponse.from_result(result.parse),
            scratch=_scratch_program_schema(scratch),
            blocks=[StructuralBlockSchema.from_block(block) for block in result.blocks],
            ir_summary=IrSummarySchema.from_summary(summary),
            static_diagnostics=[_diagnostic_schema(item) for item in analysis.diagnostics],
            quick_fixes=[_fix_schema(item) for item in analysis.quick_fixes],
            metrics=AnalysisMetricsSchema(
                methods=[_metric_schema(item) for item in analysis.metrics.methods],
                max_cyclomatic_complexity=analysis.metrics.max_cyclomatic_complexity,
                unsupported_count=analysis.metrics.unsupported_count,
            ),
            llm_configured=result.llm_configured,
            logical_review=logical,
            logical_error_count=logical_error_count,
            source_hash=result.loaded.source_hash,
        )


class ApplyLogicFixRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    source_hash: str = Field(min_length=8)
    issue_id: str = Field(min_length=1, max_length=200)
    start_byte: int = Field(ge=0)
    end_byte: int = Field(ge=0)
    expected_snippet: str
    replacement: str


class ApplyLogicFixResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    source_hash: str
    previous_source_hash: str
    issue_id: str
    has_syntax_errors: bool
    parse_diagnostic_count: int = Field(ge=0)


class RepairIssueInput(BaseModel):
    """Краткое описание ошибки для полного LLM-исправления."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=200)
    severity: str = Field(default="warning", max_length=32)
    code: str = Field(min_length=1, max_length=120)
    title: str = Field(default="", max_length=200)
    message: str = Field(default="", max_length=1000)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class RepairWithLlmRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    source_hash: str = Field(min_length=8)
    issues: list[RepairIssueInput] = Field(min_length=1, max_length=80)


class RepairWithLlmResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    source: str | None
    source_hash: str | None
    previous_source_hash: str
    fixed_issue_ids: list[str]
    notes: list[str]
    model: str | None
    has_syntax_errors: bool | None
    parse_diagnostic_count: int | None
    error_reason: str | None
    llm_configured: bool
    code_compare: CodeCompareMetricsSchema | None = None
    test_compare: BehaviorCompareSchema | None = None
    scheme_compare: SchemeCompareSchema | None = None
    original_scratch: ScratchProgramSchema | None = None
    generated_scratch: ScratchProgramSchema | None = None


class GenerateFromSchemeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    source_hash: str = Field(min_length=8)
    scratch: ScratchProgramSchema


class GenerateFromSchemeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    source: str | None
    source_hash: str | None
    previous_source_hash: str
    modules_written: list[str]
    notes: list[str]
    model: str | None
    has_syntax_errors: bool | None
    parse_diagnostic_count: int | None
    error_reason: str | None
    llm_configured: bool
    code_compare: CodeCompareMetricsSchema | None = None
    test_compare: BehaviorCompareSchema | None = None
    scheme_compare: SchemeCompareSchema | None = None
    scheme_outline: str | None = None
    original_scratch: ScratchProgramSchema | None = None
    generated_scratch: ScratchProgramSchema | None = None


def _issue_schema(issue: object) -> LlmIssueSchema:
    from app.llm.logical_review import LlmLogicalIssue

    if not isinstance(issue, LlmLogicalIssue):
        raise TypeError("ожидался LlmLogicalIssue")
    fix_schema = None
    if issue.fix is not None:
        fix = issue.fix
        fix_schema = LlmSuggestedFixSchema(
            title=fix.title,
            replacement=fix.replacement,
            start_line=fix.start_line,
            start_column=fix.start_column,
            end_line=fix.end_line,
            end_column=fix.end_column,
            start_byte=fix.start_byte,
            end_byte=fix.end_byte,
            expected_snippet=fix.expected_snippet,
            auto_applicable=fix.auto_applicable,
        )
    return LlmIssueSchema(
        id=issue.id,
        severity=issue.severity,
        code=issue.code,
        title=issue.title,
        message=issue.message,
        explanation=issue.explanation,
        start_line=issue.start_line,
        start_column=issue.start_column,
        end_line=issue.end_line,
        end_column=issue.end_column,
        start_byte=issue.start_byte,
        end_byte=issue.end_byte,
        confidence=issue.confidence,
        fix=fix_schema,
        affects_execution=bool(getattr(issue, "affects_execution", True)),
    )


def _scratch_block_schema(block: object) -> ScratchBlockSchema:
    from app.structure.scratch import ScratchBlock

    if not isinstance(block, ScratchBlock):
        raise TypeError("ожидался ScratchBlock")
    return ScratchBlockSchema(
        id=block.id,
        kind=block.kind,
        label=block.label,
        ir_node_id=block.ir_node_id,
        span=SourceSpanSchema.from_span(block.span),
        parent_id=block.parent_id,
        nest_level=block.nest_level,
        color=block.color,
        links=[ScratchLinkSchema(kind=link.kind, target_id=link.target_id) for link in block.links],
        source_snippet=block.source_snippet,
        module_id=block.module_id,
        editable=block.editable,
    )


def _scratch_program_schema(program: object) -> ScratchProgramSchema:
    from app.structure.scratch import ScratchProgram

    if not isinstance(program, ScratchProgram):
        raise TypeError("ожидался ScratchProgram")
    return ScratchProgramSchema(
        method_name=program.method_name,
        method_ir_id=program.method_ir_id,
        blocks=[_scratch_block_schema(block) for block in program.blocks],
        root_block_ids=list(program.root_block_ids),
        modules=[
            ScratchModuleSchema(
                id=module.id,
                kind=module.kind,
                name=module.name,
                parent_module_id=module.parent_module_id,
                root_block_id=module.root_block_id,
                block_ids=list(module.block_ids),
            )
            for module in program.modules
        ],
        method_names=list(program.method_names),
    )


def code_compare_schema(metrics: object | None) -> CodeCompareMetricsSchema | None:
    from app.services.code_compare import CodeCompareMetrics

    if metrics is None:
        return None
    if not isinstance(metrics, CodeCompareMetrics):
        raise TypeError("ожидался CodeCompareMetrics")
    return CodeCompareMetricsSchema(
        elapsed_ms=metrics.elapsed_ms,
        original_parse_ok=metrics.original_parse_ok,
        generated_parse_ok=metrics.generated_parse_ok,
        class_names_match=metrics.class_names_match,
        public_methods_preserved=metrics.public_methods_preserved,
        method_count_original=metrics.method_count_original,
        method_count_generated=metrics.method_count_generated,
        method_count_delta=metrics.method_count_delta,
        line_count_original=metrics.line_count_original,
        line_count_generated=metrics.line_count_generated,
        line_ratio=metrics.line_ratio,
        max_method_lines_original=metrics.max_method_lines_original,
        max_method_lines_generated=metrics.max_method_lines_generated,
        long_method_issues_original=metrics.long_method_issues_original,
        long_method_issues_generated=metrics.long_method_issues_generated,
        duplicate_logic_original=metrics.duplicate_logic_original,
        duplicate_logic_generated=metrics.duplicate_logic_generated,
        max_cyclomatic_original=metrics.max_cyclomatic_original,
        max_cyclomatic_generated=metrics.max_cyclomatic_generated,
        source_changed=metrics.source_changed,
        unsupported_original=metrics.unsupported_original,
        unsupported_generated=metrics.unsupported_generated,
        score=metrics.score,
        passed=metrics.passed,
        report_lines=list(metrics.report_lines),
    )


def scheme_compare_schema(result: object | None) -> SchemeCompareSchema | None:
    from app.structure.scheme_compare import SchemeCompareResult

    if result is None:
        return None
    if not isinstance(result, SchemeCompareResult):
        raise TypeError("ожидался SchemeCompareResult")
    return SchemeCompareSchema(
        original_block_count=result.original_block_count,
        generated_block_count=result.generated_block_count,
        original_module_count=result.original_module_count,
        generated_module_count=result.generated_module_count,
        original_method_names=list(result.original_method_names),
        generated_method_names=list(result.generated_method_names),
        methods_added=list(result.methods_added),
        methods_removed=list(result.methods_removed),
        kinds_original=dict(result.kinds_original),
        kinds_generated=dict(result.kinds_generated),
        kinds_delta=dict(result.kinds_delta),
        structural_similarity=result.structural_similarity,
        outline_original=result.outline_original,
        outline_generated=result.outline_generated,
        changed=result.changed,
        report_lines=list(result.report_lines),
    )


def behavior_compare_schema(result: object | None) -> BehaviorCompareSchema | None:
    from app.services.behavior_compare import BehaviorCompareResult

    if result is None:
        return None
    if not isinstance(result, BehaviorCompareResult):
        raise TypeError("ожидался BehaviorCompareResult")
    return BehaviorCompareSchema(
        execution_available=result.execution_available,
        execution_reason=result.execution_reason,
        tests=[
            BehaviorTestCaseSchema(
                id=item.id,
                name=item.name,
                stdin=item.stdin,
                expected_stdout=item.expected_stdout,
                expected_exit_code=item.expected_exit_code,
                main_class_hint=item.main_class_hint,
                purpose=item.purpose,
                related_issue_id=item.related_issue_id,
                expects_original_failure=item.expects_original_failure,
                description=item.description,
                error_description=item.error_description,
            )
            for item in result.tests
        ],
        runs=[
            BehaviorTestRunSchema(
                test_id=item.test_id,
                name=item.name,
                original_status=item.original_status,
                generated_status=item.generated_status,
                original_exit_code=item.original_exit_code,
                generated_exit_code=item.generated_exit_code,
                original_stdout=item.original_stdout,
                generated_stdout=item.generated_stdout,
                expected_stdout=item.expected_stdout,
                matched_expected_original=item.matched_expected_original,
                matched_expected_generated=item.matched_expected_generated,
                detail=item.detail,
                purpose=item.purpose,
                related_issue_id=item.related_issue_id,
                expects_original_failure=item.expects_original_failure,
                description=item.description,
                error_description=item.error_description,
                original_stderr=item.original_stderr,
                generated_stderr=item.generated_stderr,
                original_wall_ms=item.original_wall_ms,
                original_cpu_user_ms=item.original_cpu_user_ms,
                original_cpu_sys_ms=item.original_cpu_sys_ms,
                original_max_rss_kb=item.original_max_rss_kb,
                generated_wall_ms=item.generated_wall_ms,
                generated_cpu_user_ms=item.generated_cpu_user_ms,
                generated_cpu_sys_ms=item.generated_cpu_sys_ms,
                generated_max_rss_kb=item.generated_max_rss_kb,
                wall_ratio=item.wall_ratio,
                cpu_ratio=item.cpu_ratio,
                rss_ratio=item.rss_ratio,
                resources_vs_baseline=item.resources_vs_baseline,
            )
            for item in result.runs
        ],
        original_passed=result.original_passed,
        generated_passed=result.generated_passed,
        regressions=result.regressions,
        improvements=result.improvements,
        score=result.score,
        passed=result.passed,
        report_lines=list(result.report_lines),
        notes=list(result.notes),
    )
