"""Генерация поведенческих тестов через LLM для сравнения двух версий Java.

Запрос идёт ПОСЛЕ logical review: в промпт передаются KNOWN_ISSUES.
При сбое JSON/LLM подставляются детерминированные smoke-сценарии.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.logging import log_activity
from app.execution.java_runner import detect_main_class
from app.llm.call_options import LlmCallOptions
from app.llm.client import LlmClientError, chat_completion
from app.llm.json_extract import parse_json_object
from app.llm.prompts import build_test_scripts_messages, test_scripts_chat_payload

logger = logging.getLogger("app.llm")

_MIN_USABLE_TESTS = 3
_FALLBACK_STDINS = (
    "",
    "0\n",
    "1\n",
    "2\n",
    "-1\n",
    "10\n",
    "a\n",
    "1 2\n",
    "\n",
    "100\n",
)
_PURPOSE_WORKABILITY = "workability"
_PURPOSE_EXPLOIT = "exploit_error"


@dataclass(frozen=True, slots=True)
class BehaviorTestCase:
    id: str
    name: str
    stdin: str
    expected_stdout: str
    expected_exit_code: int
    main_class_hint: str | None = None
    purpose: str = _PURPOSE_WORKABILITY
    related_issue_id: str | None = None
    expects_original_failure: bool = False
    description: str = ""
    error_description: str = ""


@dataclass(frozen=True, slots=True)
class TestScriptsResult:
    status: str
    tests: tuple[BehaviorTestCase, ...]
    notes: tuple[str, ...]
    model: str | None
    error_reason: str | None = None


def generate_behavior_tests(
    *,
    source: str,
    options: LlmCallOptions,
    count: int = 10,
    known_issues: list[dict[str, Any]] | None = None,
) -> TestScriptsResult:
    """Запрашивает у LLM тестовые сценарии с учётом issues ревью; при сбое - fallback."""
    capped_source = source if len(source) <= 48_000 else source[:48_000] + "\n/* truncated */\n"
    issues = list(known_issues or [])
    messages = build_test_scripts_messages(source=capped_source, known_issues=issues)
    payload = test_scripts_chat_payload(
        model=options.model,
        messages=messages,
        max_tokens=8192,
        provider=options.credentials.provider,
    )
    serious = sum(1 for item in issues if str(item.get("severity", "")).lower() == "error")
    log_activity(
        "llm_test_scripts_start",
        model=options.model,
        source_chars=len(capped_source),
        known_issues=len(issues),
        serious_errors=serious,
    )
    try:
        content = chat_completion(
            credentials=options.credentials,
            base_url=options.base_url,
            oauth_url=options.oauth_url,
            payload=payload,
            timeout_seconds=min(options.timeout_seconds, 120),
            verify_ssl=options.verify_ssl,
            http_referer="http://localhost:3000",
            app_title="Java Blueprints",
        )
        data = _parse_scripts_payload(content)
        tests = _parse_tests(data.get("tests"), count=count)
        notes_raw = data.get("notes", [])
        notes = tuple(str(item) for item in notes_raw) if isinstance(notes_raw, list) else ()
        notes = (*notes, *_exploit_coverage_notes(tests, serious_errors=serious))
        if len(tests) >= count:
            log_activity(
                "llm_test_scripts_ok",
                test_count=len(tests),
                exploit_count=_exploit_count(tests),
            )
            return TestScriptsResult(
                status="ok",
                tests=tests[:count],
                notes=notes,
                model=options.model,
            )
        if len(tests) >= _MIN_USABLE_TESTS:
            padded = _pad_with_fallback(tests, source=source, count=count)
            log_activity(
                "llm_test_scripts_partial",
                test_count=len(tests),
                padded=len(padded),
                exploit_count=_exploit_count(padded),
            )
            return TestScriptsResult(
                status="ok",
                tests=padded,
                notes=(*notes, f"partial_llm_tests_{len(tests)}_padded"),
                model=options.model,
                error_reason=f"expected_{count}_got_{len(tests)}",
            )
        fallback = build_fallback_behavior_tests(source=source, count=count)
        log_activity("llm_test_scripts_fallback", reason="too_few", got=len(tests))
        return TestScriptsResult(
            status="ok",
            tests=fallback,
            notes=(*notes, "fallback_after_too_few_llm_tests"),
            model=options.model,
            error_reason=f"expected_{count}_got_{len(tests)}",
        )
    except LlmClientError as exc:
        fallback = build_fallback_behavior_tests(source=source, count=count)
        log_activity("llm_test_scripts_unavailable", reason=exc.reason, fallback=len(fallback))
        return TestScriptsResult(
            status="ok",
            tests=fallback,
            notes=("fallback_after_llm_unavailable",),
            model=options.model,
            error_reason=exc.reason,
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        fallback = build_fallback_behavior_tests(source=source, count=count)
        logger.warning(
            "llm_test_scripts_invalid error=%s fallback=%s",
            type(exc).__name__,
            len(fallback),
        )
        log_activity(
            "llm_test_scripts_fallback",
            reason=type(exc).__name__,
            fallback=len(fallback),
        )
        return TestScriptsResult(
            status="ok",
            tests=fallback,
            notes=(f"fallback_after_{type(exc).__name__}",),
            model=options.model,
            error_reason="invalid_response",
        )


def build_fallback_behavior_tests(*, source: str, count: int = 10) -> tuple[BehaviorTestCase, ...]:
    """Детерминированные smoke-входы без выдуманного эталона stdout."""
    hint = detect_main_class(source)
    capped = max(1, min(count, len(_FALLBACK_STDINS)))
    tests: list[BehaviorTestCase] = []
    for index in range(capped):
        stdin = _FALLBACK_STDINS[index]
        tests.append(
            BehaviorTestCase(
                id=f"fb{index + 1:02d}",
                name=f"smoke_{index + 1}",
                stdin=stdin,
                expected_stdout="",
                expected_exit_code=0,
                main_class_hint=hint,
                purpose=_PURPOSE_WORKABILITY,
                expects_original_failure=False,
                description="Smoke-прогон main на типовом/пустом вводе.",
                error_description="",
            )
        )
    return tuple(tests)


def _pad_with_fallback(
    tests: tuple[BehaviorTestCase, ...],
    *,
    source: str,
    count: int,
) -> tuple[BehaviorTestCase, ...]:
    if len(tests) >= count:
        return tests[:count]
    fallback = build_fallback_behavior_tests(source=source, count=count - len(tests))
    remapped = tuple(
        BehaviorTestCase(
            id=f"pad{index + 1:02d}",
            name=case.name,
            stdin=case.stdin,
            expected_stdout=case.expected_stdout,
            expected_exit_code=case.expected_exit_code,
            main_class_hint=case.main_class_hint,
            purpose=case.purpose,
            related_issue_id=case.related_issue_id,
            expects_original_failure=case.expects_original_failure,
            description=case.description,
            error_description=case.error_description,
        )
        for index, case in enumerate(fallback)
    )
    return (*tests, *remapped)[:count]


def _parse_scripts_payload(content: str) -> dict:
    """Парсит JSON; при обёртке tests на верхнем уровне нормализует."""
    data = parse_json_object(content)
    if "tests" in data:
        return data
    for key in ("test_cases", "scenarios", "cases"):
        if isinstance(data.get(key), list):
            return {"tests": data[key], "notes": [f"mapped_from_{key}"]}
    return data


def _parse_tests(raw: object, *, count: int) -> tuple[BehaviorTestCase, ...]:
    if not isinstance(raw, list):
        return ()
    tests: list[BehaviorTestCase] = []
    for index, item in enumerate(raw[: count + 2]):
        if not isinstance(item, dict):
            continue
        test_id = str(item.get("id") or f"t{index + 1:02d}")
        name = str(item.get("name") or test_id).strip() or test_id
        stdin = str(item.get("stdin") or "")
        expected = str(item.get("expected_stdout") or item.get("expected") or "")
        try:
            exit_code = int(item.get("expected_exit_code", 0))
        except (TypeError, ValueError):
            exit_code = 0
        hint_raw = item.get("main_class_hint")
        hint = str(hint_raw).strip() if isinstance(hint_raw, str) and hint_raw.strip() else None
        if hint is not None and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", hint):
            hint = None
        purpose_raw = str(item.get("purpose") or _PURPOSE_WORKABILITY).strip().lower()
        exploit_aliases = {_PURPOSE_EXPLOIT, "exploit", "bug"}
        purpose = _PURPOSE_EXPLOIT if purpose_raw in exploit_aliases else _PURPOSE_WORKABILITY
        related_raw = item.get("related_issue_id")
        related = (
            str(related_raw).strip()[:64]
            if isinstance(related_raw, str) and related_raw.strip()
            else None
        )
        expects_fail = bool(item.get("expects_original_failure")) or purpose == _PURPOSE_EXPLOIT
        if expects_fail:
            purpose = _PURPOSE_EXPLOIT
        description = str(
            item.get("description") or item.get("summary") or name
        ).strip()[:500]
        error_description = str(
            item.get("error_description")
            or item.get("error_detail")
            or item.get("bug_description")
            or ""
        ).strip()[:1200]
        tests.append(
            BehaviorTestCase(
                id=test_id[:64],
                name=name[:120],
                stdin=stdin[:4000],
                expected_stdout=expected[:8000],
                expected_exit_code=exit_code,
                main_class_hint=hint,
                purpose=purpose,
                related_issue_id=related,
                expects_original_failure=expects_fail,
                description=description,
                error_description=error_description,
            )
        )
    return tuple(tests)


def _exploit_count(tests: tuple[BehaviorTestCase, ...]) -> int:
    return sum(
        1
        for case in tests
        if case.expects_original_failure or case.purpose == _PURPOSE_EXPLOIT
    )


def _exploit_coverage_notes(
    tests: tuple[BehaviorTestCase, ...],
    *,
    serious_errors: int,
) -> tuple[str, ...]:
    exploit = _exploit_count(tests)
    if serious_errors > 0 and exploit == 0:
        return ("warning_no_exploit_despite_serious_errors",)
    if serious_errors == 0 and exploit > 0:
        return ("note_exploit_without_serious_errors",)
    if exploit > 0:
        return (f"exploit_scenarios={exploit}",)
    return ()
