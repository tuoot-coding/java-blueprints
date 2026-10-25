"""Fallback и устойчивость генерации поведенческих тестов."""

from __future__ import annotations

import json

import pytest

from app.llm import test_scripts as ts
from app.llm.call_options import LlmCallOptions
from app.llm.client import LlmClientError
from app.llm.credentials import LlmCredentials


def _options() -> LlmCallOptions:
    return LlmCallOptions(
        credentials=LlmCredentials(
            authorization_key="sk-testkey1234567890",
            provider="deepseek",
        ),
        base_url="https://api.deepseek.com",
        oauth_url="https://example.invalid",
        model="deepseek-chat",
        timeout_seconds=30.0,
        verify_ssl=True,
    )


def test_fallback_builds_ten_smoke_cases() -> None:
    cases = ts.build_fallback_behavior_tests(
        source="class Main { public static void main(String[] a) {} }",
        count=10,
    )
    assert len(cases) == 10
    assert cases[0].main_class_hint == "Main"
    assert cases[0].expected_stdout == ""


def test_generate_falls_back_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ts, "chat_completion", lambda **_kwargs: "это не json <<<")
    result = ts.generate_behavior_tests(
        source="class Main { public static void main(String[] a) {} }",
        options=_options(),
        count=10,
    )
    assert result.status == "ok"
    assert len(result.tests) == 10
    assert any("fallback" in note for note in result.notes)


def test_generate_accepts_partial_and_pads(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "tests": [
            {
                "id": f"t{i:02d}",
                "name": f"n{i}",
                "stdin": f"{i}\n",
                "expected_stdout": "",
                "expected_exit_code": 0,
            }
            for i in range(1, 5)
        ],
        "notes": [],
    }
    monkeypatch.setattr(ts, "chat_completion", lambda **_kwargs: json.dumps(payload))
    result = ts.generate_behavior_tests(
        source="class Main { public static void main(String[] a) {} }",
        options=_options(),
        count=10,
    )
    assert result.status == "ok"
    assert len(result.tests) == 10
    assert any("partial_llm_tests_4" in note for note in result.notes)


def test_generate_falls_back_on_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(**_kwargs: object) -> str:
        raise LlmClientError(reason="timeout")

    monkeypatch.setattr(ts, "chat_completion", boom)
    result = ts.generate_behavior_tests(
        source="class Main { public static void main(String[] a) {} }",
        options=_options(),
        count=10,
    )
    assert len(result.tests) == 10
    assert result.error_reason == "timeout"


def test_generate_passes_known_issues_and_parses_exploit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_chat(**kwargs: object) -> str:
        payload = kwargs.get("payload")
        assert isinstance(payload, dict)
        messages = payload.get("messages")
        assert isinstance(messages, list)
        user = messages[1]["content"]
        captured["user"] = user
        payload_out = {
            "tests": [
                {
                    "id": f"t{i:02d}",
                    "name": f"n{i}",
                    "stdin": f"{i}\n",
                    "expected_stdout": "",
                    "expected_exit_code": 0,
                    "purpose": "workability",
                    "expects_original_failure": False,
                }
                for i in range(1, 10)
            ]
            + [
                {
                    "id": "t10",
                    "name": "trigger",
                    "stdin": "bad\n",
                    "expected_stdout": "",
                    "expected_exit_code": 1,
                    "purpose": "exploit_error",
                    "related_issue_id": "e1",
                    "expects_original_failure": True,
                    "description": "Провоцирует NPE на пустом вводе",
                    "error_description": "KNOWN e1: null deref при Scanner.nextInt на bad",
                }
            ],
            "notes": [],
        }
        return json.dumps(payload_out)

    monkeypatch.setattr(ts, "chat_completion", fake_chat)
    result = ts.generate_behavior_tests(
        source="class Main { public static void main(String[] a) {} }",
        options=_options(),
        count=10,
        known_issues=[
            {
                "id": "e1",
                "severity": "error",
                "code": "llm.logic.npe",
                "title": "NPE",
                "message": "null deref",
                "start_line": 3,
                "end_line": 3,
            }
        ],
    )
    assert "KNOWN_ISSUES" in str(captured["user"])
    assert "e1|error" in str(captured["user"])
    assert result.status == "ok"
    assert len(result.tests) == 10
    assert result.tests[-1].purpose == "exploit_error"
    assert result.tests[-1].expects_original_failure is True
    assert result.tests[-1].related_issue_id == "e1"
    assert "NPE" in result.tests[-1].description
    assert "e1" in result.tests[-1].error_description
    assert any(note.startswith("exploit_scenarios=") for note in result.notes)
