from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ApplicationError
from app.schemas.errors import ErrorCode
from app.storage.sqlite import SqliteProjectStore

CREATE_PATH = "/api/v1/projects"


def test_store_create_get_and_revision_conflict(tmp_path: Path) -> None:
    store = SqliteProjectStore(tmp_path / "projects.sqlite3")
    store.init_schema()
    created = store.create_project("class A {}\n", "A.java")
    assert created.revision.id == 1
    assert created.revision.parent_revision is None
    loaded = store.get_project(created.id)
    assert loaded.revision.source == "class A {}\n"
    assert loaded.file_name == "A.java"

    updated = store.put_revision(created.id, "class B {}\n", expected_revision=1)
    assert updated.id == 2
    assert updated.parent_revision == 1
    assert store.get_project(created.id).revision.source == "class B {}\n"

    with pytest.raises(ApplicationError) as conflict:
        store.put_revision(created.id, "class C {}\n", expected_revision=1)
    assert conflict.value.error_code == ErrorCode.REVISION_CONFLICT
    assert conflict.value.details == {"expected_revision": 1, "actual_revision": 2}
    assert store.get_project(created.id).revision.source == "class B {}\n"


def test_store_rejects_path_like_file_name_and_unknown_project(tmp_path: Path) -> None:
    store = SqliteProjectStore(tmp_path / "projects.sqlite3")
    store.init_schema()
    with pytest.raises(ApplicationError) as invalid:
        store.create_project("class A {}", "../A.java")
    assert invalid.value.error_code == ErrorCode.VALIDATION_ERROR
    with pytest.raises(ApplicationError) as missing:
        store.get_project("../secret")
    assert missing.value.error_code == ErrorCode.NOT_FOUND
    assert not (tmp_path / "secret").exists()
    assert not (tmp_path / "A.java").exists()


def test_project_api_round_trip_and_conflict(client: TestClient) -> None:
    created = client.post(
        CREATE_PATH, json={"source": "class Пример {}\n", "file_name": "Demo.java"}
    )
    assert created.status_code == 201
    payload = created.json()
    project_id = payload["project_id"]
    assert payload["revision"] == 1
    assert payload["file_name"] == "Demo.java"

    fetched = client.get(f"{CREATE_PATH}/{project_id}")
    assert fetched.status_code == 200
    assert fetched.json()["source"] == "class Пример {}\n"

    updated = client.put(
        f"{CREATE_PATH}/{project_id}/source",
        json={"source": "class Next {}\n", "expected_revision": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["parent_revision"] == 1

    conflict = client.put(
        f"{CREATE_PATH}/{project_id}/source",
        json={"source": "class Lost {}\n", "expected_revision": 1},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "revision_conflict"
    assert client.get(f"{CREATE_PATH}/{project_id}").json()["source"] == "class Next {}\n"


def test_project_api_rejects_bad_name_missing_project_and_oversize(
    client: TestClient, tmp_path: Path
) -> None:
    bad_name = client.post(CREATE_PATH, json={"source": "class A {}", "file_name": "../A.java"})
    assert bad_name.status_code == 422
    assert bad_name.json()["error_code"] == "validation_error"

    missing = client.get(f"{CREATE_PATH}/{'a' * 32}")
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "not_found"

    from tests.conftest import authed_client, build_test_settings

    limited = build_test_settings(tmp_path).model_copy(update={"max_java_source_bytes": 4})
    with authed_client(limited) as limited_client:
        response = limited_client.post(
            CREATE_PATH,
            json={"source": "class A {}", "file_name": "A.java"},
        )
    assert response.status_code == 413
    assert response.json()["error_code"] == "payload_too_large"
