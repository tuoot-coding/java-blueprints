from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.application import create_app
from tests.conftest import build_test_settings
from tests.java_fixtures import read_java_fixture

PATH = "/api/v1/graph/build"


def test_graph_build_for_named_method(client: TestClient) -> None:
    response = client.post(
        PATH,
        json={"source": read_java_fixture("control_flow.java"), "method_name": "loop"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["method_name"] == "loop"
    assert body["partial"] is False
    assert body["entry_id"]
    assert body["exit_id"]
    assert body["coordinate_system"] == "line_utf16_column_1_based_half_open"
    kinds = {edge["kind"] for edge in body["edges"]}
    assert {"normal", "true", "false", "loop_back"} <= kinds


def test_graph_without_method_name_selects_first(client: TestClient) -> None:
    response = client.post(PATH, json={"source": read_java_fixture("control_flow.java")})
    assert response.status_code == 200
    body = response.json()
    assert body["method_name"] == "branch"
    assert any(item["code"] == "selected_first_method" for item in body["limitations"])


def test_graph_unknown_method_is_not_found(client: TestClient) -> None:
    response = client.post(
        PATH,
        json={"source": read_java_fixture("simple_method.java"), "method_name": "missing"},
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "not_found"


def test_graph_try_is_partial(client: TestClient) -> None:
    response = client.post(
        PATH,
        json={"source": read_java_fixture("try_statement.java"), "method_name": "m"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["partial"] is True
    assert any(item["code"] == "method_cfg_partial" for item in body["limitations"])


def test_graph_rejects_oversized_source(tmp_path: Path) -> None:
    from tests.conftest import authed_client

    limited = build_test_settings(tmp_path).model_copy(update={"max_java_source_bytes": 4})
    with authed_client(limited) as client:
        response = client.post(PATH, json={"source": "class A {}"})
    assert response.status_code == 413
    assert response.json()["error_code"] == "payload_too_large"
