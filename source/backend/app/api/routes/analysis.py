"""POST /api/v1/analysis/analyze."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_settings_dependency
from app.core.config import Settings
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.schemas.errors import ErrorResponse
from app.services.analysis import analyze_source_request

router = APIRouter(prefix="/analysis", tags=["analysis"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {"model": ErrorResponse, "description": "Исходник превышает лимит размера."},
    422: {"model": ErrorResponse, "description": "Ошибка валидации тела запроса."},
}


@router.post(
    "/analyze",
    operation_id="analyze_java_source",
    summary="Статический анализ Java",
    response_model=AnalyzeResponse,
    responses=_ERROR_RESPONSES,
)
def analyze_java(
    body: AnalyzeRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> AnalyzeResponse:
    """Возвращает структурные диагностики, quick fix и метрики сложности."""
    run, loaded = analyze_source_request(
        body.source,
        max_source_bytes=settings.max_java_source_bytes,
    )
    return AnalyzeResponse.from_run(
        run,
        source_hash=loaded.source_hash,
        has_syntax_errors=loaded.inspection.result.has_syntax_errors,
    )
