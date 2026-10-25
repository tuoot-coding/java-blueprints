"""Оркестрация проектов: лимит размера и SQLite-ревизии."""

from __future__ import annotations

from app.core.config import Settings
from app.domain.models import Project, Revision
from app.services.source_guard import ensure_java_source_size
from app.storage.sqlite import SqliteProjectStore


def create_project_request(source: str, file_name: str, settings: Settings) -> Project:
    ensure_java_source_size(source, max_source_bytes=settings.max_java_source_bytes)
    return _store(settings).create_project(source, file_name)


def get_project_request(project_id: str, settings: Settings) -> Project:
    return _store(settings).get_project(project_id)


def update_project_source_request(
    project_id: str,
    source: str,
    expected_revision: int,
    settings: Settings,
) -> Revision:
    ensure_java_source_size(source, max_source_bytes=settings.max_java_source_bytes)
    return _store(settings).put_revision(project_id, source, expected_revision)


def _store(settings: Settings) -> SqliteProjectStore:
    store = SqliteProjectStore(settings.database_path)
    store.init_schema()
    return store
