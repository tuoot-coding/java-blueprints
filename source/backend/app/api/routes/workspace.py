"""Workspace: inspect + apply logic fix + repair with LLM + generate from scheme."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_settings_dependency
from app.core.config import Settings
from app.core.logging import log_activity
from app.schemas.errors import ErrorResponse
from app.schemas.workspace import (
    ApplyLogicFixRequest,
    ApplyLogicFixResponse,
    GenerateFromSchemeRequest,
    GenerateFromSchemeResponse,
    RepairWithLlmRequest,
    RepairWithLlmResponse,
    WorkspaceInspectRequest,
    WorkspaceInspectResponse,
    _scratch_program_schema,
    behavior_compare_schema,
    code_compare_schema,
)
from app.services.logic_fix import apply_logic_fix_request
from app.services.repair import repair_workspace_request
from app.services.scheme_codegen import (
    generate_from_scheme_request,
    scratch_program_from_payload,
)
from app.services.workspace import inspect_workspace_request

router = APIRouter(prefix="/workspace", tags=["workspace"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorResponse, "description": "Конфликт ревизии или патч неприменим."},
    413: {"model": ErrorResponse, "description": "Исходник превышает лимит размера."},
    422: {"model": ErrorResponse, "description": "Ошибка валидации тела запроса."},
    503: {"model": ErrorResponse, "description": "LLM недоступен или не настроен."},
}


@router.post(
    "/inspect",
    operation_id="inspect_workspace",
    summary="Разбор, модульная блок-схема и логический анализ",
    response_model=WorkspaceInspectResponse,
    responses=_ERROR_RESPONSES,
)
def inspect_workspace(
    body: WorkspaceInspectRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> WorkspaceInspectResponse:
    """Синтаксис, модульная логическая схема и список логических ошибок LLM."""
    log_activity("http_workspace_inspect", include_llm=body.include_llm)
    effective = settings
    if not body.include_llm and settings.llm_enabled:
        effective = settings.model_copy(update={"llm_enabled": False})
    result = inspect_workspace_request(body.source, effective)
    return WorkspaceInspectResponse.from_result(result)


@router.post(
    "/apply-logic-fix",
    operation_id="apply_logic_fix",
    summary="Применить LLM-исправление логической ошибки",
    response_model=ApplyLogicFixResponse,
    responses=_ERROR_RESPONSES,
)
def apply_logic_fix(
    body: ApplyLogicFixRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> ApplyLogicFixResponse:
    """Точечный патч с проверкой source_hash и expected_snippet, затем повторный parse."""
    log_activity("http_apply_logic_fix", issue_id=body.issue_id)
    result = apply_logic_fix_request(
        source=body.source,
        source_hash=body.source_hash,
        issue_id=body.issue_id,
        start_byte=body.start_byte,
        end_byte=body.end_byte,
        expected_snippet=body.expected_snippet,
        replacement=body.replacement,
        max_source_bytes=settings.max_java_source_bytes,
    )
    return ApplyLogicFixResponse(
        source=result.source,
        source_hash=result.source_hash,
        previous_source_hash=result.previous_source_hash,
        issue_id=result.issue_id,
        has_syntax_errors=result.has_syntax_errors,
        parse_diagnostic_count=result.parse_diagnostic_count,
    )


@router.post(
    "/repair-with-llm",
    operation_id="repair_workspace_with_llm",
    summary="Отправить код в LLM для исправления выявленных ошибок",
    response_model=RepairWithLlmResponse,
    responses=_ERROR_RESPONSES,
)
def repair_with_llm(
    body: RepairWithLlmRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> RepairWithLlmResponse:
    """Возвращает Java-файл с исправлениями и сравнительные проверки."""
    log_activity("http_repair_with_llm", issue_count=len(body.issues))
    result = repair_workspace_request(
        source=body.source,
        source_hash=body.source_hash,
        issues=[item.model_dump() for item in body.issues],
        settings=settings,
    )
    return RepairWithLlmResponse(
        status=result.status,
        source=result.source,
        source_hash=result.source_hash,
        previous_source_hash=result.previous_source_hash,
        fixed_issue_ids=list(result.fixed_issue_ids),
        notes=list(result.notes),
        model=result.model,
        has_syntax_errors=result.has_syntax_errors,
        parse_diagnostic_count=result.parse_diagnostic_count,
        error_reason=result.error_reason,
        llm_configured=result.llm_configured,
        code_compare=code_compare_schema(result.code_compare),
        test_compare=behavior_compare_schema(result.test_compare),
        scheme_compare=None,
        original_scratch=(
            _scratch_program_schema(result.original_scratch)
            if result.original_scratch is not None
            else None
        ),
        generated_scratch=(
            _scratch_program_schema(result.generated_scratch)
            if result.generated_scratch is not None
            else None
        ),
    )


@router.post(
    "/generate-from-scheme",
    operation_id="generate_java_from_scheme",
    summary="Рекурсивная генерация Java по отредактированной модульной схеме",
    response_model=GenerateFromSchemeResponse,
    responses=_ERROR_RESPONSES,
)
def generate_from_scheme(
    body: GenerateFromSchemeRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> GenerateFromSchemeResponse:
    """По сохранению логической схемы строит соответствующий Java через LLM."""
    log_activity(
        "http_generate_from_scheme",
        blocks=len(body.scratch.blocks),
        modules=len(body.scratch.modules),
    )
    program = scratch_program_from_payload(body.scratch.model_dump())
    result = generate_from_scheme_request(
        source=body.source,
        source_hash=body.source_hash,
        program=program,
        settings=settings,
    )
    return GenerateFromSchemeResponse(
        status=result.status,
        source=result.source,
        source_hash=result.source_hash,
        previous_source_hash=result.previous_source_hash,
        modules_written=list(result.modules_written),
        notes=list(result.notes),
        model=result.model,
        has_syntax_errors=result.has_syntax_errors,
        parse_diagnostic_count=result.parse_diagnostic_count,
        error_reason=result.error_reason,
        llm_configured=result.llm_configured,
        code_compare=code_compare_schema(result.code_compare),
        test_compare=behavior_compare_schema(result.test_compare),
        scheme_compare=None,
        scheme_outline=result.scheme_outline,
        original_scratch=(
            _scratch_program_schema(result.original_scratch)
            if result.original_scratch is not None
            else None
        ),
        generated_scratch=(
            _scratch_program_schema(result.generated_scratch)
            if result.generated_scratch is not None
            else None
        ),
    )
