"""Фильтрация ложных срабатываний logical review."""

from __future__ import annotations

from app.llm.logical_review import LlmLogicalIssue, _drop_false_positives_local


def _issue(*, explanation: str, issue_id: str = "e1") -> LlmLogicalIssue:
    return LlmLogicalIssue(
        id=issue_id,
        severity="error",
        code="llm.logic.test",
        title="t",
        message="m",
        explanation=explanation,
        start_line=1,
        start_column=1,
        end_line=1,
        end_column=2,
        start_byte=0,
        end_byte=1,
        confidence="high",
        fix=None,
        affects_execution=True,
    )


def test_drop_false_positive_by_explanation() -> None:
    kept, dropped = _drop_false_positives_local(
        (
            _issue(explanation="Это не является ошибкой, код корректен", issue_id="fp"),
            _issue(explanation="Гарантированный NPE на null", issue_id="real"),
        )
    )
    assert dropped == 1
    assert len(kept) == 1
    assert kept[0].id == "real"


def test_keep_real_error_explanations() -> None:
    kept, dropped = _drop_false_positives_local(
        (_issue(explanation="Сравнение строк через == ломает equals"),)
    )
    assert dropped == 0
    assert len(kept) == 1
