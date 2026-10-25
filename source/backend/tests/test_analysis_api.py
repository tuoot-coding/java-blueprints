from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.application import create_app
from tests.conftest import build_test_settings
from tests.java_fixtures import read_java_fixture

PATH = "/api/v1/analysis/analyze"


def test_analyze_returns_unreachable_fix_and_metrics(client: TestClient) -> None:
    response = client.post(PATH, json={"source": read_java_fixture("unreachable.java")})
    assert response.status_code == 200
    body = response.json()
    assert body["coordinate_system"] == "line_utf16_column_1_based_half_open"
    assert body["has_syntax_errors"] is False
    rules = {item["rule_id"] for item in body["diagnostics"]}
    assert "java.unreachable_statement" in rules
    assert body["quick_fixes"]
    assert body["quick_fixes"][0]["title"] == "Удалить недостижимый оператор"
    assert body["metrics"]["methods"][0]["cyclomatic_complexity"] >= 1
    assert body["metrics"]["methods"][0]["cfg_partial"] is False


def test_analyze_reports_complexity_and_anonymous_unsupported(client: TestClient) -> None:
    complex_response = client.post(PATH, json={"source": read_java_fixture("complexity.java")})
    assert complex_response.status_code == 200
    assert complex_response.json()["metrics"]["max_cyclomatic_complexity"] >= 10
    anon_response = client.post(
        PATH,
        json={"source": read_java_fixture("unsupported_anonymous.java")},
    )
    assert anon_response.status_code == 200
    rules = {item["rule_id"] for item in anon_response.json()["diagnostics"]}
    assert "java.unsupported_construct" in rules
    assert anon_response.json()["metrics"]["unsupported_count"] >= 1


def test_analyze_rejects_oversized_source(tmp_path: Path) -> None:
    from tests.conftest import authed_client

    limited = build_test_settings(tmp_path).model_copy(update={"max_java_source_bytes": 4})
    with authed_client(limited) as client:
        response = client.post(PATH, json={"source": "class A {}"})
    assert response.status_code == 413
    assert response.json()["error_code"] == "payload_too_large"
