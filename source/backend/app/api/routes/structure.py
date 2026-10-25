"""POST /api/v1/structure/build."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_settings_dependency
from app.core.config import Settings
from app.schemas.errors import ErrorResponse
from app.schemas.structure import (
    IrSummarySchema,
    StructuralBlockSchema,
    StructureBuildRequest,
    StructureBuildResponse,
)
from app.services.structure import build_structure_request

router = APIRouter(prefix="/structure", tags=["structure"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {"model": ErrorResponse, "description": "Исходник превышает лимит размера."},
    422: {"model": ErrorResponse, "description": "Ошибка валидации тела запроса."},
}


@router.post(
    "/build",
    operation_id="build_structure",
    summary="Структурные блоки Java",
    response_model=StructureBuildResponse,
    responses=_ERROR_RESPONSES,
)
def build_structure(
    body: StructureBuildRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> StructureBuildResponse:
    """Строит блоки по tree-sitter IR. Синтаксические ошибки Java не дают HTTP 500."""
    result = build_structure_request(
        body.source,
        max_source_bytes=settings.max_java_source_bytes,
    )
    return StructureBuildResponse(
        blocks=[StructuralBlockSchema.from_block(block) for block in result.blocks],
        ir_summary=IrSummarySchema.from_summary(result.ir_summary),
        unsupported_count=result.unsupported_count,
        source_hash=result.source_hash,
        has_syntax_errors=result.has_syntax_errors,
    )
