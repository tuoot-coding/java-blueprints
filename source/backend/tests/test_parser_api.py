from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.schemas.parser import ParseJavaResponse
from tests.conftest import authed_client, build_test_settings

PARSE_PATH = "/api/v1/parser/parse"


def test_parse_valid_java_returns_ok(client: TestClient) -> None:
    response = client.post(PARSE_PATH, json={"source": "class Ok {}"})
    assert response.status_code == 200
    body = ParseJavaResponse.model_validate(response.json())
    assert body.status == "ok"
    assert body.has_syntax_errors is False
    assert body.diagnostics == []
    assert body.root.type == "program"
    assert body.grammar == "tree-sitter-java"
    assert body.coordinate_system == "line_utf16_column_1_based_half_open"


def test_parse_invalid_java_returns_200_with_diagnostics(client: TestClient) -> None:
    response = client.post(PARSE_PATH, json={"source": "class Bad { void m() {"})
    assert response.status_code == 200
    body = ParseJavaResponse.model_validate(response.json())
    assert body.status == "syntax_errors"
    assert body.has_syntax_errors is True
    assert len(body.diagnostics) >= 1
    assert "traceback" not in response.text.lower()


def test_parse_empty_source_allowed(client: TestClient) -> None:
    response = client.post(PARSE_PATH, json={"source": ""})
    assert response.status_code == 200
    body = ParseJavaResponse.model_validate(response.json())
    assert body.source_byte_length == 0


def test_parse_missing_source_is_validation_error(client: TestClient) -> None:
    response = client.post(PARSE_PATH, json={})
    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "validation_error"
    assert "traceback" not in response.text.lower()


def test_parse_wrong_source_type_is_validation_error(client: TestClient) -> None:
    response = client.post(PARSE_PATH, json={"source": 123})
    assert response.status_code == 422
    assert response.json()["error_code"] == "validation_error"


def test_parse_invalid_json_is_validation_or_bad_request(client: TestClient) -> None:
    response = client.post(
        PARSE_PATH,
        content=b"{not-json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code in {400, 422}
    assert "traceback" not in response.text.lower()


def test_parse_rejects_oversized_source(tmp_path: Path) -> None:
    limited = build_test_settings(tmp_path).model_copy(update={"max_java_source_bytes": 32})
    with authed_client(limited) as client:
        response = client.post(PARSE_PATH, json={"source": "a" * 64})
    assert response.status_code == 413
    payload = response.json()
    assert payload["error_code"] == "payload_too_large"
    assert payload["details"]["max_source_bytes"] == 32
    assert "traceback" not in response.text.lower()


def test_parse_accepts_large_but_allowed_source(client: TestClient) -> None:
    source = "class Big {\n" + ("  // x\n" * 2000) + "}\n"
    assert len(source.encode("utf-8")) < 1_048_576
    response = client.post(PARSE_PATH, json={"source": source})
    assert response.status_code == 200
    body = ParseJavaResponse.model_validate(response.json())
    assert body.status == "ok"


def test_parse_cyrillic_source_round_trip_bytes(client: TestClient) -> None:
    source = 'class Пример { String s = "текст"; }\n'
    response = client.post(PARSE_PATH, json={"source": source})
    assert response.status_code == 200
    body = ParseJavaResponse.model_validate(response.json())
    assert body.source_byte_length == len(source.encode("utf-8"))
    assert body.status == "ok"


def test_openapi_includes_parse_endpoint() -> None:
    from app.openapi_export import build_openapi_document

    document = build_openapi_document()
    assert "/api/v1/parser/parse" in document["paths"]
    assert "post" in document["paths"]["/api/v1/parser/parse"]
    schemas = document["components"]["schemas"]
    assert "ParseJavaRequest" in schemas
    assert "ParseJavaResponse" in schemas
    assert "SyntaxDiagnostic" in schemas
