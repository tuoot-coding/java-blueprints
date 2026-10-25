from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.application import create_app
from tests.conftest import build_test_settings
from tests.java_fixtures import read_java_fixture

PATH = "/api/v1/structure/build"


def test_structure_build_returns_blocks_and_hash(client: TestClient) -> None:
    source = read_java_fixture("simple_method.java")
    response = client.post(PATH, json={"source": source})
    assert response.status_code == 200
    body = response.json()
    assert body["coordinate_system"] == "line_utf16_column_1_based_half_open"
    assert body["source_hash"] == hashlib.sha256(source.encode("utf-8")).hexdigest()
    assert body["has_syntax_errors"] is False
    assert body["unsupported_count"] == 0
    types = {block["type"] for block in body["blocks"]}
    assert "class_declaration" in types
    assert "method_declaration" in types
    method = next(block for block in body["blocks"] if block["label"] == "метод add")
    assert method["editable"] is False
    assert method["supported_operations"] == []
    assert method["parent_id"] is not None
    assert any(link["kind"] == "parameters" for link in method["links"])

    sequenced = client.post(PATH, json={"source": read_java_fixture("unreachable.java")})
    assert sequenced.status_code == 200
    blocks = sequenced.json()["blocks"]
    assert any(link["kind"] == "next" for block in blocks for link in block["links"])


def test_structure_reports_unsupported_anonymous(client: TestClient) -> None:
    response = client.post(PATH, json={"source": read_java_fixture("unsupported_anonymous.java")})
    assert response.status_code == 200
    body = response.json()
    assert body["unsupported_count"] >= 1
    assert any(block["type"] == "unsupported" for block in body["blocks"])


def test_structure_models_switch(client: TestClient) -> None:
    response = client.post(PATH, json={"source": read_java_fixture("unsupported_switch.java")})
    assert response.status_code == 200
    body = response.json()
    assert body["unsupported_count"] == 0
    assert any(
        block["type"] in {"switch", "switch_expression"} for block in body["blocks"]
    )


def test_structure_rejects_oversized_source(tmp_path: Path) -> None:
    from tests.conftest import authed_client

    limited = build_test_settings(tmp_path).model_copy(update={"max_java_source_bytes": 8})
    with authed_client(limited) as client:
        response = client.post(PATH, json={"source": "class Big {}"})
    assert response.status_code == 413
    assert response.json()["error_code"] == "payload_too_large"
