"""POST /api/v1/transform/generate."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_settings_dependency
from app.core.config import Settings
from app.schemas.errors import ErrorResponse
from app.schemas.transform import GenerateRequest, GenerateResponse
from app.services.transform import generate_java_request

router = APIRouter(prefix="/transform", tags=["transform"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {"model": ErrorResponse, "description": "Исходник превышает лимит размера."},
    422: {"model": ErrorResponse, "description": "Генерация отклонена или тело запроса неверно."},
}


@router.post(
    "/generate",
    operation_id="generate_java",
    summary="Структурная генерация Java",
    response_model=GenerateResponse,
    responses=_ERROR_RESPONSES,
)
def generate_java(
    body: GenerateRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> GenerateResponse:
    """Возвращает исходный текст, если IR полностью поддержан. Иначе 422."""
    source, source_hash = generate_java_request(
        body.source,
        max_source_bytes=settings.max_java_source_bytes,
    )
    return GenerateResponse(source=source, source_hash=source_hash)
