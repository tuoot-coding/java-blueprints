from __future__ import annotations

from app.llm.json_extract import parse_json_object
from app.llm.response_normalize import normalize_review_payload


def test_parse_json_object_from_fence() -> None:
    raw = '```json\n{"issues":[],"notes":["ok"]}\n```'
    data = parse_json_object(raw)
    assert data["notes"] == ["ok"]


def test_parse_json_object_with_preamble() -> None:
    raw = (
        'Вот результат:\n{"issues":[{"id":"1","severity":"warning",'
        '"code":"llm.logic.x","title":"t","message":"m"}],"notes":[]}'
    )
    data = parse_json_object(raw)
    assert len(data["issues"]) == 1


def test_parse_json_object_trailing_commas() -> None:
    raw = (
        '{"tests":[{"id":"t01","name":"a","stdin":"",'
        '"expected_stdout":"","expected_exit_code":0,},], "notes":[],}'
    )
    data = parse_json_object(raw)
    assert len(data["tests"]) == 1


def test_parse_json_object_unwrapped_array() -> None:
    raw = (
        '[{"id":"t01","name":"a","stdin":"1\\n",'
        '"expected_stdout":"1","expected_exit_code":0}]'
    )
    data = parse_json_object(raw)
    assert len(data["tests"]) == 1
    assert data["notes"] == ["unwrapped_array"]


def test_normalize_review_accepts_numeric_confidence() -> None:
    normalized = normalize_review_payload(
        {
            "issues": [
                {
                    "id": "a",
                    "severity": "error",
                    "code": "logic.bug",
                    "title": "t",
                    "message": "m",
                    "confidence": 0.9,
                    "start_line": 2,
                }
            ],
            "notes": ["n"],
        }
    )
    issue = normalized["issues"][0]
    assert issue["code"].startswith("llm.")
    assert issue["confidence"] == "high"
    assert issue["start_line"] == 2
