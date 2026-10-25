from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.application import create_app
from tests.conftest import build_test_settings
from tests.java_fixtures import read_java_fixture

ANALYZE_PATH = "/api/v1/analysis/analyze"
FIX_PATH = "/api/v1/fixes/apply"
GENERATE_PATH = "/api/v1/transform/generate"


def test_apply_fix_endpoint_reparses_source(client: TestClient) -> None:
    source = read_java_fixture("unreachable.java")
    analyzed = client.post(ANALYZE_PATH, json={"source": source})
    assert analyzed.status_code == 200
    payload = analyzed.json()
    fix = payload["quick_fixes"][0]
    response = client.post(
        FIX_PATH,
        json={
            "source": source,
            "fix_id": fix["id"],
            "expected_source_hash": payload["source_hash"],
            "expected_start_byte": fix["start_byte"],
            "expected_end_byte": fix["end_byte"],
            "expected_text": fix["expected_text"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "int x = 1;" not in body["source"]
    assert body["status"] == "ok"
    assert body["has_syntax_errors"] is False
    assert body["source_hash"] != payload["source_hash"]


def test_apply_fix_rejects_stale_hash(client: TestClient) -> None:
    source = read_java_fixture("unreachable.java")
    analyzed = client.post(ANALYZE_PATH, json={"source": source}).json()
    fix = analyzed["quick_fixes"][0]
    response = client.post(
        FIX_PATH,
        json={
            "source": source,
            "fix_id": fix["id"],
            "expected_source_hash": "a" * 64,
            "expected_start_byte": fix["start_byte"],
            "expected_end_byte": fix["end_byte"],
            "expected_text": fix["expected_text"],
        },
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "fix_not_applicable"


def test_generate_identity_for_supported_source(client: TestClient) -> None:
    source = read_java_fixture("simple_method.java")
    response = client.post(GENERATE_PATH, json={"source": source})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == source
    assert body["mode"] == "identity_original_source"


def test_generate_accepts_modeled_switch(client: TestClient) -> None:
    source = read_java_fixture("unsupported_switch.java")
    response = client.post(GENERATE_PATH, json={"source": source})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == source
    assert body["mode"] == "identity_original_source"


def test_generate_refuses_unsupported_anonymous(client: TestClient) -> None:
    response = client.post(
        GENERATE_PATH,
        json={"source": read_java_fixture("unsupported_anonymous.java")},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "generation_refused"
    assert body["details"]["unsupported_count"] >= 1
    assert "traceback" not in response.text.lower()


def test_generate_rejects_oversized_source(tmp_path: Path) -> None:
    from tests.conftest import authed_client

    limited = build_test_settings(tmp_path).model_copy(update={"max_java_source_bytes": 4})
    with authed_client(limited) as client:
        response = client.post(GENERATE_PATH, json={"source": "class A {}"})
    assert response.status_code == 413
    assert response.json()["error_code"] == "payload_too_large"
