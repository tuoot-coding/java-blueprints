"""POST /api/v1/fixes/apply."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_settings_dependency
from app.core.config import Settings
from app.schemas.errors import ErrorResponse
from app.schemas.fixes import ApplyFixRequest, ApplyFixResponse
from app.services.fixes import apply_fix_request

router = APIRouter(prefix="/fixes", tags=["fixes"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorResponse, "description": "Исправление не применимо к этому тексту."},
    413: {"model": ErrorResponse, "description": "Исходник превышает лимит размера."},
    422: {"model": ErrorResponse, "description": "Ошибка валидации тела запроса."},
}


@router.post(
    "/apply",
    operation_id="apply_quick_fix",
    summary="Применить quick fix",
    response_model=ApplyFixResponse,
    responses=_ERROR_RESPONSES,
)
def apply_fix(
    body: ApplyFixRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> ApplyFixResponse:
    """Применяет совпавший fix и возвращает результат повторного разбора."""
    applied = apply_fix_request(
        body.source,
        fix_id=body.fix_id,
        expected_source_hash=body.expected_source_hash,
        expected_start_byte=body.expected_start_byte,
        expected_end_byte=body.expected_end_byte,
        expected_text=body.expected_text,
        max_source_bytes=settings.max_java_source_bytes,
    )
    return ApplyFixResponse.from_applied(applied)
