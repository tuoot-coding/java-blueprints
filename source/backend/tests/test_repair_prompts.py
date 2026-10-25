from __future__ import annotations

from app.llm.prompts import format_issues_for_repair
from app.llm.repair import _normalize_java


def test_format_issues_is_compact() -> None:
    text = format_issues_for_repair(
        [
            {
                "id": "issue_1",
                "severity": "error",
                "code": "llm.logic.eq",
                "title": "Сравнение",
                "message": "Используйте equals",
                "start_line": 10,
                "end_line": 12,
            }
        ]
    )
    assert "issue_1|error|llm.logic.eq|L10-12|" in text
    assert "equals" in text


def test_normalize_java_strips_fences() -> None:
    raw = "```java\nclass A {}\n```"
    assert _normalize_java(raw).startswith("class A")
