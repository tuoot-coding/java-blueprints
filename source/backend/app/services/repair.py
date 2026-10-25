"""Оркестрация полного LLM-исправления выявленных ошибок через GigaChat."""

from __future__ import annotations

from dataclasses import dataclass, replace
from http import HTTPStatus
from typing import Any

from app.analysis.engine import run_static_analysis
from app.core.config import Settings
from app.core.errors import ApplicationError
from app.core.logging import log_activity
from app.graph.builder import build_method_cfg
from app.ir.builder import build_structural_ir
from app.ir.query import list_methods
from app.llm.call_options import resolve_llm_options
from app.llm.repair import RepairResult, repair_java_source
from app.llm.source_pack import build_repair_source_pack
from app.parser.service import inspect_java_source, parse_java_source
from app.schemas.errors import ErrorCode
from app.services.behavior_compare import BehaviorCompareResult, compare_versions_with_tests
from app.services.code_compare import CodeCompareMetrics
from app.services.inspection import load_java
from app.structure.scratch import ScratchProgram, build_scratch_program
from app.texts.errors import llm_failure_error_code
from app.transform.fingerprint import source_fingerprint


@dataclass(frozen=True, slots=True)
class RepairRequestResult:
    status: str
    source: str | None
    source_hash: str | None
    previous_source_hash: str
    fixed_issue_ids: tuple[str, ...]
    notes: tuple[str, ...]
    model: str | None
    has_syntax_errors: bool | None
    parse_diagnostic_count: int | None
    error_reason: str | None
    llm_configured: bool
    code_compare: CodeCompareMetrics | None = None
    test_compare: BehaviorCompareResult | None = None
    original_scratch: ScratchProgram | None = None
    generated_scratch: ScratchProgram | None = None


def repair_workspace_request(
    *,
    source: str,
    source_hash: str,
    issues: list[dict[str, Any]],
    settings: Settings,
) -> RepairRequestResult:
    loaded = load_java(source, max_source_bytes=settings.max_java_source_bytes)
    current_hash = loaded.source_hash
    log_activity(
        "workspace_repair_start",
        issue_count=len(issues),
        source_hash=current_hash[:16],
    )
    if current_hash != source_hash:
        log_activity(
            "workspace_repair_stale_source",
            expected=source_hash[:16],
            actual=current_hash[:16],
        )
        raise ApplicationError(
            ErrorCode.REVISION_CONFLICT,
            status_code=HTTPStatus.CONFLICT,
            details={"expected_source_hash": source_hash, "actual_source_hash": current_hash},
        )

    options = resolve_llm_options(settings)
    if options is None:
        raise ApplicationError(
            llm_failure_error_code("llm_not_configured"),
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            details={"reason": "llm_not_configured"},
        )

    original_scratch = build_scratch_program(loaded.ir)

    if loaded.inspection.result.has_syntax_errors:
        log_activity("workspace_repair_skipped_syntax_errors")
        return RepairRequestResult(
            status="skipped_syntax_errors",
            source=None,
            source_hash=None,
            previous_source_hash=current_hash,
            fixed_issue_ids=(),
            notes=("Исправление через LLM пропущено: есть синтаксические ошибки.",),
            model=settings.llm_model,
            has_syntax_errors=True,
            parse_diagnostic_count=len(loaded.inspection.result.diagnostics),
            error_reason="syntax_errors",
            llm_configured=True,
            original_scratch=original_scratch,
        )

    if not issues:
        return RepairRequestResult(
            status="no_issues",
            source=None,
            source_hash=None,
            previous_source_hash=current_hash,
            fixed_issue_ids=(),
            notes=("Нет ошибок для исправления.",),
            model=settings.llm_model,
            has_syntax_errors=False,
            parse_diagnostic_count=0,
            error_reason="no_issues",
            llm_configured=True,
            original_scratch=original_scratch,
        )

    source_pack = build_repair_source_pack(loaded.source, loaded.ir)
    call_options = options
    if source_pack.truncated:
        call_options = replace(
            options,
            timeout_seconds=min(300.0, max(options.timeout_seconds, options.timeout_seconds * 1.5)),
        )

    static_summary = _static_summary(loaded.source, loaded.ir)
    repair: RepairResult = repair_java_source(
        source_pack=source_pack,
        issues=issues,
        options=call_options,
        static_summary=static_summary,
        original_source=loaded.source,
    )

    if repair.status != "ok" or repair.java_source is None:
        log_activity(
            "workspace_repair_failed",
            status=repair.status,
            reason=repair.error_reason,
        )
        if repair.status == "unavailable":
            reason = repair.error_reason or "unavailable"
            raise ApplicationError(
                llm_failure_error_code(reason),
                status_code=HTTPStatus.PAYMENT_REQUIRED
                if reason == "http_402"
                else HTTPStatus.SERVICE_UNAVAILABLE,
                details={"reason": reason},
            )
        return RepairRequestResult(
            status=repair.status,
            source=None,
            source_hash=None,
            previous_source_hash=current_hash,
            fixed_issue_ids=(),
            notes=repair.notes,
            model=repair.model,
            has_syntax_errors=None,
            parse_diagnostic_count=None,
            error_reason=repair.error_reason,
            llm_configured=True,
            original_scratch=original_scratch,
        )

    repaired = repair.java_source
    if len(repaired.encode("utf-8")) > settings.max_java_source_bytes:
        raise ApplicationError(
            ErrorCode.PAYLOAD_TOO_LARGE,
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            details={"max_source_bytes": settings.max_java_source_bytes},
        )

    parse_result = parse_java_source(repaired)
    # Повторная попытка, если LLM вернул синтаксически битый код.
    if parse_result.has_syntax_errors:
        retry_issues = [
            *issues,
            {
                "id": "syntax_retry",
                "severity": "error",
                "code": "java.syntax_error",
                "title": "Синтаксис после repair",
                "message": (
                    "Предыдущий ответ LLM содержал синтаксические ошибки. "
                    "Исправь все issues и синтаксис."
                ),
                "start_line": 1,
                "end_line": 1,
            },
        ]
        retry_pack = build_repair_source_pack(
            repaired, build_structural_ir(repaired, inspect_java_source(repaired).tree)
        )
        retry = repair_java_source(
            source_pack=retry_pack,
            issues=retry_issues,
            options=call_options,
            static_summary="повтор после syntax_errors",
            original_source=repaired,
        )
        if retry.status == "ok" and retry.java_source:
            repaired = retry.java_source
            parse_result = parse_java_source(repaired)
            repair = RepairResult(
                status=retry.status,
                java_source=repaired,
                fixed_issue_ids=tuple(
                    dict.fromkeys([*repair.fixed_issue_ids, *retry.fixed_issue_ids])
                ),
                notes=(*repair.notes, *retry.notes, "retry_after_syntax_errors"),
                model=retry.model,
            )

    # Регрессионный барьер: если после фикса стало хуже по static - одна доработка.
    repaired, repair, parse_result = _guard_against_regression(
        original_source=loaded.source,
        original_ir=loaded.ir,
        repaired=repaired,
        repair=repair,
        issues=issues,
        options=call_options,
        parse_result=parse_result,
    )

    inspection = inspect_java_source(repaired)
    generated_ir = build_structural_ir(repaired, inspection.tree)
    generated_scratch = build_scratch_program(generated_ir)
    # Тесты ПОСЛЕ ревью: сценарии с учётом выбранных issues исходника.
    test_compare = compare_versions_with_tests(
        original=loaded.source,
        generated=repaired,
        options=call_options,
        known_issues=issues,
    )
    code_compare = test_compare.code_metrics
    new_hash = source_fingerprint(repaired)
    notes = (*repair.notes, *test_compare.notes)
    log_activity(
        "workspace_repair_ok",
        fixed_count=len(repair.fixed_issue_ids),
        new_source_hash=new_hash[:16],
        has_syntax_errors=parse_result.has_syntax_errors,
        code_score=code_compare.score if code_compare else None,
        test_score=test_compare.score,
        test_passed=test_compare.passed,
    )
    return RepairRequestResult(
        status="ok",
        source=repaired,
        source_hash=new_hash,
        previous_source_hash=current_hash,
        fixed_issue_ids=repair.fixed_issue_ids,
        notes=notes,
        model=repair.model,
        has_syntax_errors=parse_result.has_syntax_errors,
        parse_diagnostic_count=len(parse_result.diagnostics),
        error_reason=None,
        llm_configured=True,
        code_compare=code_compare,
        test_compare=test_compare,
        original_scratch=original_scratch,
        generated_scratch=generated_scratch,
    )


def _static_summary(source: str, ir: object) -> str:
    from app.ir.models import IrNode

    if not isinstance(ir, IrNode):
        return ""
    methods = list_methods(ir)
    graphs = {method.id: build_method_cfg(method) for method in methods}
    analysis = run_static_analysis(ir, graphs, source=source)
    rules = sorted({item.rule_id for item in analysis.diagnostics})
    return (
        f"static_diagnostics={len(analysis.diagnostics)} "
        f"rules={','.join(rules) or '-'} "
        f"max_cyclo={analysis.metrics.max_cyclomatic_complexity}"
    )


def _static_error_count(source: str, ir: object) -> int:
    from app.ir.models import IrNode

    if not isinstance(ir, IrNode):
        return 0
    methods = list_methods(ir)
    graphs = {method.id: build_method_cfg(method) for method in methods}
    analysis = run_static_analysis(ir, graphs, source=source)
    return sum(1 for item in analysis.diagnostics if str(item.severity) == "error")


def _guard_against_regression(
    *,
    original_source: str,
    original_ir: object,
    repaired: str,
    repair: RepairResult,
    issues: list[dict[str, Any]],
    options: object,
    parse_result: object,
) -> tuple[str, RepairResult, object]:
    """Если появились syntax errors или выросло число static error - один retry."""
    from app.llm.call_options import LlmCallOptions

    if not isinstance(options, LlmCallOptions):
        return repaired, repair, parse_result

    before_errors = _static_error_count(original_source, original_ir)
    after_parse = parse_java_source(repaired)
    if after_parse.has_syntax_errors:
        # Уже был retry в caller; здесь только фиксируем.
        return repaired, repair, after_parse

    after_ir = build_structural_ir(repaired, inspect_java_source(repaired).tree)
    after_errors = _static_error_count(repaired, after_ir)
    if after_errors <= before_errors:
        return repaired, repair, after_parse

    log_activity(
        "workspace_repair_regression_retry",
        before_static_errors=before_errors,
        after_static_errors=after_errors,
    )
    retry_issues = [
        *issues,
        {
            "id": "regression_guard",
            "severity": "error",
            "code": "llm.structure.regression",
            "title": "Регрессия после исправления",
            "message": (
                f"После правки static error выросло: {before_errors} -> {after_errors}. "
                "Верни исправление без новых логических/структурных ошибок. "
                "Минимальный diff, все self_tests=pass."
            ),
            "start_line": 1,
            "end_line": 1,
        },
    ]
    retry_pack = build_repair_source_pack(repaired, after_ir)
    retry = repair_java_source(
        source_pack=retry_pack,
        issues=retry_issues,
        options=options,
        static_summary=_static_summary(repaired, after_ir),
        original_source=repaired,
    )
    if retry.status != "ok" or not retry.java_source:
        return repaired, repair, after_parse
    candidate = retry.java_source
    candidate_parse = parse_java_source(candidate)
    if candidate_parse.has_syntax_errors:
        return repaired, repair, after_parse
    candidate_ir = build_structural_ir(candidate, inspect_java_source(candidate).tree)
    candidate_errors = _static_error_count(candidate, candidate_ir)
    if candidate_errors > after_errors:
        return repaired, repair, after_parse
    merged = RepairResult(
        status="ok",
        java_source=candidate,
        fixed_issue_ids=tuple(dict.fromkeys([*repair.fixed_issue_ids, *retry.fixed_issue_ids])),
        notes=(*repair.notes, *retry.notes, "regression_guard_applied"),
        model=retry.model,
        self_tests=retry.self_tests,
    )
    return candidate, merged, candidate_parse
