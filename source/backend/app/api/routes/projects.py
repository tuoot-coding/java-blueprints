"""Проекты и ревизии исходника."""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_settings_dependency
from app.core.config import Settings
from app.schemas.errors import ErrorResponse
from app.schemas.projects import (
    CreateProjectRequest,
    ProjectCreatedResponse,
    ProjectResponse,
    RevisionResponse,
    UpdateSourceRequest,
)
from app.services.projects import (
    create_project_request,
    get_project_request,
    update_project_source_request,
)

router = APIRouter(prefix="/projects", tags=["projects"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Проект не найден."},
    409: {"model": ErrorResponse, "description": "Конфликт ожидаемой ревизии."},
    413: {"model": ErrorResponse, "description": "Исходник превышает лимит размера."},
    422: {"model": ErrorResponse, "description": "Ошибка валидации тела запроса."},
}


@router.post(
    "",
    operation_id="create_project",
    summary="Создать проект",
    response_model=ProjectCreatedResponse,
    status_code=HTTPStatus.CREATED,
    responses=_ERROR_RESPONSES,
)
def create_project(
    body: CreateProjectRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> ProjectCreatedResponse:
    """Сохраняет исходник как ревизию 1. Имя файла не используется как путь."""
    project = create_project_request(body.source, body.file_name, settings)
    return ProjectCreatedResponse.from_project(project)


@router.get(
    "/{project_id}",
    operation_id="get_project",
    summary="Получить проект",
    response_model=ProjectResponse,
    responses=_ERROR_RESPONSES,
)
def get_project(
    project_id: str,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> ProjectResponse:
    """Возвращает текущую ревизию проекта."""
    project = get_project_request(project_id, settings)
    return ProjectResponse.from_project(project)


@router.put(
    "/{project_id}/source",
    operation_id="update_project_source",
    summary="Сохранить новую ревизию исходника",
    response_model=RevisionResponse,
    responses=_ERROR_RESPONSES,
)
def update_project_source(
    project_id: str,
    body: UpdateSourceRequest,
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> RevisionResponse:
    """Пишет ревизию, только если expected_revision совпадает с текущей."""
    revision = update_project_source_request(
        project_id,
        body.source,
        body.expected_revision,
        settings,
    )
    return RevisionResponse.from_revision(revision)
