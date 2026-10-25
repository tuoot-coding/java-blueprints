"""Корневой маршрутизатор /api/v1."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.routes import (
    analysis,
    auth,
    fixes,
    graph,
    health,
    parser,
    projects,
    structure,
    transform,
    workspace,
)
from app.core.metadata import API_V1_PREFIX
from app.schemas.errors import ErrorResponse

_COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера."},
}

api_router = APIRouter(prefix=API_V1_PREFIX, responses=_COMMON_ERROR_RESPONSES)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(parser.router)
api_router.include_router(structure.router)
api_router.include_router(graph.router)
api_router.include_router(analysis.router)
api_router.include_router(fixes.router)
api_router.include_router(transform.router)
api_router.include_router(projects.router)
api_router.include_router(workspace.router)
