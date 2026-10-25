"""POST /api/v1/graph/build."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_settings_dependency
from app.core.config import Settings
from app.schemas.errors import ErrorResponse
from app.schemas.graph import GraphBuildRequest, GraphBuildResponse
from app.services.graph import build_graph_request

router = APIRouter(prefix="/graph", tags=["graph"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Метод с таким именем не найден."},
    413: {"model": ErrorResponse, "description": "Исходник превышает лимит размера."},
    422: {"model": ErrorResponse, "description": "Ошибка валидации тела запроса."},
}


@router.post(
    "/build",
    operation_id="build_graph",
    summary="CFG метода",
    response_model=GraphBuildResponse,
    responses=_ERROR_RESPONSES,
)
def build_graph(
    body: GraphBuildRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> GraphBuildResponse:
    """Строит CFG одного метода. Неполные конструкции помечены limitations."""
    graph, source_hash, has_syntax_errors = build_graph_request(
        body.source,
        method_name=body.method_name,
        max_source_bytes=settings.max_java_source_bytes,
    )
    return GraphBuildResponse.from_graph(
        graph,
        source_hash=source_hash,
        has_syntax_errors=has_syntax_errors,
    )
