from __future__ import annotations

from fastapi.testclient import TestClient


def test_workspace_inspect_builds_scratch_without_llm(client: TestClient) -> None:
    source = """
class Demo {
  int abs(int n) {
    if (n < 0) {
      return -n;
    }
    return n;
  }
}
"""
    response = client.post(
        "/api/v1/workspace/inspect",
        json={"source": source, "include_llm": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parse"]["status"] == "ok"
    assert body["scratch"]["method_name"] == "abs"
    assert len(body["scratch"]["blocks"]) >= 2
    kinds = {block["kind"] for block in body["scratch"]["blocks"]}
    assert "method" in kinds
    assert "if" in kinds
    assert body["llm_configured"] is False
    assert body["logical_review"] is None
    assert body["logical_error_count"] == 0


def test_apply_logic_fix_rejects_stale_hash(client: TestClient) -> None:
    source = "class A { int m() { return 1; } }"
    response = client.post(
        "/api/v1/workspace/apply-logic-fix",
        json={
            "source": source,
            "source_hash": "0" * 64,
            "issue_id": "issue_1",
            "start_byte": 0,
            "end_byte": 1,
            "expected_snippet": "c",
            "replacement": "C",
        },
    )
    assert response.status_code == 409


def test_repair_with_llm_rejects_stale_hash(client: TestClient) -> None:
    source = "class A { int m() { return 1; } }"
    response = client.post(
        "/api/v1/workspace/repair-with-llm",
        json={
            "source": source,
            "source_hash": "0" * 64,
            "issues": [
                {
                    "id": "issue_1",
                    "severity": "error",
                    "code": "llm.logic.test",
                    "title": "тест",
                    "message": "ошибка",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
        },
    )
    assert response.status_code == 409


def test_repair_with_llm_requires_configured_key(client: TestClient) -> None:
    from app.transform.fingerprint import source_fingerprint

    source = "class A { int m() { return 1; } }"
    response = client.post(
        "/api/v1/workspace/repair-with-llm",
        json={
            "source": source,
            "source_hash": source_fingerprint(source),
            "issues": [
                {
                    "id": "issue_1",
                    "severity": "warning",
                    "code": "llm.logic.x",
                    "title": "x",
                    "message": "y",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
        },
    )
    # Без ключа в тестовом окружении ожидаем 503 llm_unavailable.
    assert response.status_code == 503
    assert response.json()["error_code"] == "llm_unavailable"
