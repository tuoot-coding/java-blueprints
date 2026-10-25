"""Проект и ревизия исходника. Исходный текст хранится в ревизии, не в графе."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from app.transform.fingerprint import source_fingerprint

ProjectId = NewType("ProjectId", str)


@dataclass(frozen=True, slots=True)
class Revision:
    """Подтвержденная ревизия. source_hash вычисляется, в таблице его нет."""

    id: int
    project_id: ProjectId
    source: str
    parent_revision: int | None
    created_at: str

    @property
    def source_hash(self) -> str:
        return source_fingerprint(self.source)


@dataclass(frozen=True, slots=True)
class Project:
    id: ProjectId
    file_name: str
    created_at: str
    revision: Revision
