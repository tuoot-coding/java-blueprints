"""SQLite-хранилище проектов и ревизий.

Путь к файлу базы берется только из Settings.database_path.
Имя файла проекта - метаданные строки, оно не открывается как путь на диске.
Исходник лежит в столбце revisions.source.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

from app.core.errors import ApplicationError
from app.domain.models import Project, ProjectId, Revision
from app.schemas.errors import ErrorCode

_FILE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
_PROJECT_ID = re.compile(r"^[0-9a-f]{32}$")
_PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""
_REVISIONS_TABLE = """
CREATE TABLE IF NOT EXISTS revisions (
    id INTEGER NOT NULL,
    project_id TEXT NOT NULL,
    source TEXT NOT NULL,
    parent_revision INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (project_id, id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
"""


class SqliteProjectStore:
    """Локальная база проектов. Каждый вызов открывает свое соединение."""

    def __init__(self, database_path: Path) -> None:
        resolved = database_path.expanduser().resolve()
        if resolved.suffix not in {".sqlite3", ".sqlite", ".db"}:
            raise ValueError("файл базы должен оканчиваться на .sqlite3, .sqlite или .db")
        self._path = resolved

    @property
    def database_path(self) -> Path:
        return self._path

    def init_schema(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._session() as connection:
            connection.execute(_PROJECTS_TABLE)
            connection.execute(_REVISIONS_TABLE)

    def create_project(self, source: str, file_name: str) -> Project:
        safe_name = validate_file_name(file_name)
        project_id = ProjectId(uuid.uuid4().hex)
        created_at = _timestamp()
        with self._session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO projects (id, file_name, created_at) VALUES (?, ?, ?)",
                (project_id, safe_name, created_at),
            )
            connection.execute(
                """
                INSERT INTO revisions (id, project_id, source, parent_revision, created_at)
                VALUES (?, ?, ?, NULL, ?)
                """,
                (1, project_id, source, created_at),
            )
        revision = Revision(
            id=1,
            project_id=project_id,
            source=source,
            parent_revision=None,
            created_at=created_at,
        )
        return Project(
            id=project_id,
            file_name=safe_name,
            created_at=created_at,
            revision=revision,
        )

    def get_project(self, project_id: str) -> Project:
        if _PROJECT_ID.fullmatch(project_id) is None:
            raise _not_found()
        with self._session() as connection:
            row = connection.execute(
                """
                SELECT
                    p.id AS project_id,
                    p.file_name AS file_name,
                    p.created_at AS project_created_at,
                    r.id AS revision_id,
                    r.source AS source,
                    r.parent_revision AS parent_revision,
                    r.created_at AS revision_created_at
                FROM projects AS p
                JOIN revisions AS r ON r.project_id = p.id
                WHERE p.id = ?
                ORDER BY r.id DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            raise _not_found()
        typed_id = ProjectId(str(row["project_id"]))
        revision = Revision(
            id=int(row["revision_id"]),
            project_id=typed_id,
            source=str(row["source"]),
            parent_revision=(
                None if row["parent_revision"] is None else int(row["parent_revision"])
            ),
            created_at=str(row["revision_created_at"]),
        )
        return Project(
            id=typed_id,
            file_name=str(row["file_name"]),
            created_at=str(row["project_created_at"]),
            revision=revision,
        )

    def put_revision(self, project_id: str, source: str, expected_revision: int) -> Revision:
        """Пишет следующую ревизию, только если текущая равна expected_revision."""
        if _PROJECT_ID.fullmatch(project_id) is None:
            raise _not_found()
        typed_id = ProjectId(project_id)
        created_at = _timestamp()
        with self._session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project_row = connection.execute(
                "SELECT id FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project_row is None:
                raise _not_found()
            current = connection.execute(
                "SELECT MAX(id) AS revision_id FROM revisions WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            actual = (
                None
                if current is None or current["revision_id"] is None
                else int(current["revision_id"])
            )
            if actual != expected_revision:
                raise ApplicationError(
                    ErrorCode.REVISION_CONFLICT,
                    status_code=HTTPStatus.CONFLICT,
                    details={
                        "expected_revision": expected_revision,
                        "actual_revision": actual,
                    },
                )
            new_id = expected_revision + 1
            connection.execute(
                """
                INSERT INTO revisions (id, project_id, source, parent_revision, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (new_id, project_id, source, expected_revision, created_at),
            )
        return Revision(
            id=new_id,
            project_id=typed_id,
            source=source,
            parent_revision=expected_revision,
            created_at=created_at,
        )

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            if connection.in_transaction:
                connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()


def validate_file_name(file_name: str) -> str:
    """Принимает одно безопасное имя. Каталоги и '..' отклоняются."""
    if (
        _FILE_NAME.fullmatch(file_name) is None
        or file_name in {".", ".."}
        or ".." in file_name
        or "/" in file_name
        or "\\" in file_name
    ):
        raise ApplicationError(
            ErrorCode.VALIDATION_ERROR,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            details={"field": "file_name"},
        )
    return file_name


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _not_found() -> ApplicationError:
    return ApplicationError(ErrorCode.NOT_FOUND, status_code=HTTPStatus.NOT_FOUND)
