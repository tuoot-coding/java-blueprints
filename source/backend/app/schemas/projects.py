"""Схемы проектов и ревизий исходника."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models import Project, Revision

_FILE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    file_name: str = Field(min_length=1, max_length=120)

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, value: str) -> str:
        if _FILE_NAME.fullmatch(value) is None or value in {".", ".."} or ".." in value:
            raise ValueError("недопустимое имя файла")
        return value


class UpdateSourceRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    expected_revision: int = Field(ge=1)


class ProjectCreatedResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    file_name: str
    revision: int
    source_hash: str
    created_at: str

    @classmethod
    def from_project(cls, project: Project) -> ProjectCreatedResponse:
        return cls(
            project_id=project.id,
            file_name=project.file_name,
            revision=project.revision.id,
            source_hash=project.revision.source_hash,
            created_at=project.created_at,
        )


class ProjectResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    file_name: str
    revision: int
    parent_revision: int | None
    source: str
    source_hash: str
    created_at: str
    project_created_at: str

    @classmethod
    def from_project(cls, project: Project) -> ProjectResponse:
        return cls(
            project_id=project.id,
            file_name=project.file_name,
            revision=project.revision.id,
            parent_revision=project.revision.parent_revision,
            source=project.revision.source,
            source_hash=project.revision.source_hash,
            created_at=project.revision.created_at,
            project_created_at=project.created_at,
        )


class RevisionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    revision: int
    parent_revision: int | None
    source_hash: str

    @classmethod
    def from_revision(cls, revision: Revision) -> RevisionResponse:
        return cls(
            project_id=revision.project_id,
            revision=revision.id,
            parent_revision=revision.parent_revision,
            source_hash=revision.source_hash,
        )
