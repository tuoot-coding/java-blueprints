"""Строгая нормализация JSON-ответов LLM к ожидаемым структурам."""

from __future__ import annotations

from typing import Any


def normalize_review_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Приводит ответ review к {issues: list[dict], notes: list[str]}."""
    issues_raw = data.get("issues")
    if issues_raw is None and isinstance(data.get("problems"), list):
        issues_raw = data["problems"]
    if not isinstance(issues_raw, list):
        issues_raw = []
    issues: list[dict[str, Any]] = []
    for index, item in enumerate(issues_raw):
        if not isinstance(item, dict):
            continue
        issues.append(_normalize_issue(item, index))
    notes_raw = data.get("notes", [])
    notes = [str(item) for item in notes_raw] if isinstance(notes_raw, list) else []
    return {"issues": issues, "notes": notes}


def normalize_repair_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Приводит ответ repair к java/replacements/fixed_issue_ids/notes."""
    java = data.get("java")
    if java is not None and not isinstance(java, str):
        java = str(java) if java else None
    replacements_raw = data.get("replacements", [])
    replacements: list[dict[str, Any]] = []
    if isinstance(replacements_raw, list):
        for item in replacements_raw:
            if not isinstance(item, dict):
                continue
            try:
                start = int(item["start_line"])
                end = int(item["end_line"])
            except (KeyError, TypeError, ValueError):
                continue
            replacement = item.get("replacement")
            if not isinstance(replacement, str):
                continue
            replacements.append(
                {"start_line": start, "end_line": end, "replacement": replacement}
            )
    fixed_raw = data.get("fixed_issue_ids", data.get("fixed", []))
    fixed_ids = (
        [str(item) for item in fixed_raw if str(item).strip()]
        if isinstance(fixed_raw, list)
        else []
    )
    notes_raw = data.get("notes", [])
    notes = [str(item) for item in notes_raw] if isinstance(notes_raw, list) else []
    self_tests_raw = data.get("self_tests", [])
    self_tests: list[dict[str, Any]] = []
    if isinstance(self_tests_raw, list):
        for item in self_tests_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            status = str(item.get("status") or "").strip().lower()
            if not name:
                continue
            if status not in {"pass", "fail"}:
                status = "fail"
            self_tests.append(
                {
                    "name": name,
                    "status": status,
                    "detail": str(item.get("detail") or ""),
                }
            )
    return {
        "java": java,
        "replacements": replacements,
        "fixed_issue_ids": fixed_ids,
        "notes": notes,
        "self_tests": self_tests,
    }


def self_tests_all_passed(self_tests: list[dict[str, Any]]) -> bool:
    """True, если есть хотя бы один тест и все со status=pass."""
    if not self_tests:
        return False
    return all(item.get("status") == "pass" for item in self_tests)


def _normalize_issue(item: dict[str, Any], index: int) -> dict[str, Any]:
    severity = _normalize_severity(str(item.get("severity", "warning")))
    confidence_raw = item.get("confidence", "medium")
    if isinstance(confidence_raw, (int, float)):
        confidence = "high" if float(confidence_raw) >= 0.75 else "medium"
    else:
        confidence = str(confidence_raw).lower()
        if confidence not in {"high", "medium"}:
            confidence = "medium"
    code = str(item.get("code", "llm.logic.issue"))
    if not code.startswith("llm."):
        code = f"llm.logic.{code}"
    affects = _resolve_affects_execution(item, code=code, severity=severity)
    # Структура всегда в корзине structure; критичная complexity остаётся error.
    if not affects and severity != "error":
        severity = "structure"
        if code.startswith("llm.logic."):
            code = "llm.structure." + code.removeprefix("llm.logic.")
    elif severity == "structure":
        affects = False
    start_line = _as_int(item.get("start_line"), 1)
    start_column = _as_int(item.get("start_column"), 1)
    end_line = max(start_line, _as_int(item.get("end_line"), start_line))
    end_column = max(1, _as_int(item.get("end_column"), start_column + 1))
    fix = item.get("fix")
    if fix is not None and not isinstance(fix, dict):
        fix = None
    return {
        "id": str(item.get("id") or f"issue_{index + 1}"),
        "severity": severity,
        "affects_execution": affects,
        "code": code,
        "title": str(item.get("title") or item.get("name") or "Логическая проблема"),
        "message": str(item.get("message") or item.get("description") or ""),
        "explanation": str(item.get("explanation") or ""),
        "start_line": start_line,
        "start_column": start_column,
        "end_line": end_line,
        "end_column": end_column,
        "confidence": confidence,
        "fix": fix,
    }


def _normalize_severity(raw: str) -> str:
    value = raw.lower().strip()
    if value in {"structur", "structural", "info", "hint"}:
        return "structure"
    if value in {"error", "warning", "structure"}:
        return value
    return "warning"


def _resolve_affects_execution(
    item: dict[str, Any],
    *,
    code: str,
    severity: str,
) -> bool:
    raw = item.get("affects_execution")
    if isinstance(raw, bool):
        return raw
    if severity in {"structure", "info", "hint"}:
        return False
    # Критичная complexity (Big O) помечается error и влияет на оценку качества.
    if code.startswith("llm.complexity.") and severity == "error":
        return True
    if code.startswith(("llm.structure.", "llm.bloat.")):
        return False
    if code.startswith("llm.complexity."):
        return False
    return True


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
