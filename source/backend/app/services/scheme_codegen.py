"""Оркестрация: схема -> outline -> LLM Java + поведенческие тесты."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.core.logging import log_activity
from app.ir.builder import build_structural_ir
from app.ir.models import SourceSpan
from app.llm.call_options import resolve_llm_options
from app.llm.scheme_codegen import SchemeCodegenResult, generate_java_from_modular_scheme
from app.parser.service import inspect_java_source, parse_java_source
from app.schemas.errors import ErrorCode
from app.services.behavior_compare import BehaviorCompareResult, compare_versions_with_tests
from app.services.code_compare import CodeCompareMetrics
from app.services.inspection import load_java
from app.structure.scratch import (
    ScratchBlock,
    ScratchLink,
    ScratchModule,
    ScratchProgram,
    build_scratch_program,
    serialize_scratch_outline,
)
from app.texts.errors import llm_failure_error_code
from app.transform.fingerprint import source_fingerprint


@dataclass(frozen=True, slots=True)
class SchemeCodegenRequestResult:
    status: str
    source: str | None
    source_hash: str | None
    previous_source_hash: str
    modules_written: tuple[str, ...]
    notes: tuple[str, ...]
    model: str | None
    has_syntax_errors: bool | None
    parse_diagnostic_count: int | None
    error_reason: str | None
    llm_configured: bool
    code_compare: CodeCompareMetrics | None
    test_compare: BehaviorCompareResult | None
    scheme_outline: str | None
    original_scratch: ScratchProgram | None
    generated_scratch: ScratchProgram | None


def generate_from_scheme_request(
    *,
    source: str,
    source_hash: str,
    program: ScratchProgram,
    settings: Settings,
) -> SchemeCodegenRequestResult:
    loaded = load_java(source, max_source_bytes=settings.max_java_source_bytes)
    current_hash = loaded.source_hash
    outline = serialize_scratch_outline(program)
    log_activity(
        "workspace_scheme_codegen_start",
        blocks=len(program.blocks),
        modules=len(program.modules),
        outline_chars=len(outline),
        source_hash=current_hash[:16],
    )
    if current_hash != source_hash:
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
    result: SchemeCodegenResult = generate_java_from_modular_scheme(
        program=program,
        source=loaded.source,
        options=options,
    )
    if result.status != "ok" or result.java_source is None:
        if result.status == "unavailable":
            reason = result.error_reason or "unavailable"
            raise ApplicationError(
                llm_failure_error_code(reason),
                status_code=HTTPStatus.PAYMENT_REQUIRED
                if reason == "http_402"
                else HTTPStatus.SERVICE_UNAVAILABLE,
                details={"reason": reason},
            )
        return SchemeCodegenRequestResult(
            status=result.status,
            source=None,
            source_hash=None,
            previous_source_hash=current_hash,
            modules_written=(),
            notes=result.notes,
            model=result.model,
            has_syntax_errors=None,
            parse_diagnostic_count=None,
            error_reason=result.error_reason,
            llm_configured=True,
            code_compare=None,
            test_compare=None,
            scheme_outline=outline,
            original_scratch=original_scratch,
            generated_scratch=None,
        )

    generated = result.java_source
    if len(generated.encode("utf-8")) > settings.max_java_source_bytes:
        raise ApplicationError(
            ErrorCode.PAYLOAD_TOO_LARGE,
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            details={"max_source_bytes": settings.max_java_source_bytes},
        )

    parse_result = parse_java_source(generated)
    inspection = inspect_java_source(generated)
    generated_ir = build_structural_ir(generated, inspection.tree)
    generated_scratch = build_scratch_program(generated_ir)

    # Схема без списка issues ревью: только workability-сценарии по исходнику.
    test_compare = compare_versions_with_tests(
        original=loaded.source,
        generated=generated,
        options=options,
        known_issues=[],
    )
    code_compare = test_compare.code_metrics
    new_hash = source_fingerprint(generated)
    notes = (*result.notes, *test_compare.notes, "awaiting_user_replace_confirm")
    log_activity(
        "workspace_scheme_codegen_ok",
        new_source_hash=new_hash[:16],
        code_score=code_compare.score if code_compare else None,
        test_score=test_compare.score,
        has_syntax_errors=parse_result.has_syntax_errors,
        mode="llm_scheme",
    )
    return SchemeCodegenRequestResult(
        status="ok",
        source=generated,
        source_hash=new_hash,
        previous_source_hash=current_hash,
        modules_written=result.modules_written,
        notes=notes,
        model=result.model,
        has_syntax_errors=parse_result.has_syntax_errors,
        parse_diagnostic_count=len(parse_result.diagnostics),
        error_reason=None,
        llm_configured=True,
        code_compare=code_compare,
        test_compare=test_compare,
        scheme_outline=outline,
        original_scratch=original_scratch,
        generated_scratch=generated_scratch,
    )


def scratch_program_from_payload(payload: dict) -> ScratchProgram:
    """Собирает ScratchProgram из JSON тела запроса клиента."""
    blocks_raw = payload.get("blocks") or []
    modules_raw = payload.get("modules") or []
    blocks: list[ScratchBlock] = []
    for item in blocks_raw:
        span_raw = item.get("span") or {}
        span = SourceSpan(
            start_byte=int(span_raw.get("start_byte", 0)),
            end_byte=int(span_raw.get("end_byte", 0)),
            start_line=int(span_raw.get("start_line", 1)),
            start_column=int(span_raw.get("start_column", 1)),
            end_line=int(span_raw.get("end_line", 1)),
            end_column=int(span_raw.get("end_column", 1)),
        )
        links = tuple(
            ScratchLink(kind=str(link.get("kind", "next")), target_id=str(link.get("target_id")))
            for link in (item.get("links") or [])
            if link.get("target_id")
        )
        blocks.append(
            ScratchBlock(
                id=str(item["id"]),
                kind=str(item.get("kind", "expression")),
                label=str(item.get("label", "")),
                ir_node_id=str(item.get("ir_node_id", item["id"])),
                span=span,
                parent_id=item.get("parent_id"),
                nest_level=int(item.get("nest_level", 0)),
                color=str(item.get("color", "#475569")),
                links=links,
                source_snippet=str(item.get("source_snippet", "")),
                module_id=item.get("module_id"),
                editable=bool(item.get("editable", True)),
            )
        )
    modules = tuple(
        ScratchModule(
            id=str(item["id"]),
            kind=str(item.get("kind", "method")),
            name=str(item.get("name", "?")),
            parent_module_id=item.get("parent_module_id"),
            root_block_id=str(item.get("root_block_id", item["id"])),
            block_ids=tuple(str(block_id) for block_id in (item.get("block_ids") or [])),
        )
        for item in modules_raw
        if item.get("id")
    )
    method_names = tuple(str(name) for name in (payload.get("method_names") or []) if name)
    if not method_names:
        method_names = tuple(module.name for module in modules if module.kind == "method")
    return ScratchProgram(
        method_name=payload.get("method_name"),
        method_ir_id=payload.get("method_ir_id"),
        blocks=tuple(blocks),
        root_block_ids=tuple(str(item) for item in (payload.get("root_block_ids") or [])),
        modules=modules,
        method_names=method_names,
    )
