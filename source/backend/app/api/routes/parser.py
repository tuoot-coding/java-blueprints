"""POST /api/v1/parser/parse."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_settings_dependency
from app.core.config import Settings
from app.schemas.errors import ErrorResponse
from app.schemas.parser import ParseJavaRequest, ParseJavaResponse
from app.services.parser import parse_java_source_request

router = APIRouter(prefix="/parser", tags=["parser"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {"model": ErrorResponse, "description": "Исходник превышает лимит размера."},
    422: {"model": ErrorResponse, "description": "Ошибка валидации тела запроса."},
}


@router.post(
    "/parse",
    operation_id="parse_java_source",
    summary="Синтаксический разбор Java",
    response_model=ParseJavaResponse,
    responses=_ERROR_RESPONSES,
)
def parse_java(
    body: ParseJavaRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> ParseJavaResponse:
    """Разбирает Java через tree-sitter-java. Синтаксические ошибки не дают HTTP 500."""
    result = parse_java_source_request(
        body.source,
        max_source_bytes=settings.max_java_source_bytes,
    )
    return ParseJavaResponse.from_result(result)
