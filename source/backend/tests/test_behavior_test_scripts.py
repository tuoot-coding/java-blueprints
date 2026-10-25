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
