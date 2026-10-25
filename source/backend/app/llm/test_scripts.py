"""Генерация поведенческих тестов через LLM для сравнения двух версий Java.

При сбое JSON/LLM подставляются детерминированные smoke-сценарии, чтобы
Docker-сравнение всё равно выполнялось.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class BehaviorTestCase:
    id: str
    name: str
    stdin: str
    expected_stdout: str
    expected_exit_code: int
    main_class_hint: str | None = None


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
) -> TestScriptsResult:
    """Запрашивает у LLM тестовые сценарии; при сбое - fallback smoke-набор."""
    capped_source = source if len(source) <= 48_000 else source[:48_000] + "\n/* truncated */\n"
    messages = build_test_scripts_messages(source=capped_source)
    payload = test_scripts_chat_payload(
        model=options.model,
        messages=messages,
        max_tokens=8192,
        provider=options.credentials.provider,
    )
    log_activity("llm_test_scripts_start", model=options.model, source_chars=len(capped_source))
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
        if len(tests) >= count:
            log_activity("llm_test_scripts_ok", test_count=len(tests))
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
            )
            return TestScriptsResult(
                status="ok",
                tests=padded,
                notes=(*notes, f"partial_llm_tests_{len(tests)}_padded"),
                model=options.model,
                error_reason=f"expected_{count}_got_{len(tests)}",
            )
        # Мало тестов от LLM - дополняем fallback и всё равно гоняем.
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
    """Детерминированные smoke-входы без выдуманного эталона stdout.

    expected_stdout пустой: сравнение считает совпадение по exit_code
    (обычно 0) - обе версии должны хотя бы успешно запускаться на одних входах.
    """
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
    # Перенумеруем id fallback, чтобы не пересекались.
    remapped = tuple(
        BehaviorTestCase(
            id=f"pad{index + 1:02d}",
            name=case.name,
            stdin=case.stdin,
            expected_stdout=case.expected_stdout,
            expected_exit_code=case.expected_exit_code,
            main_class_hint=case.main_class_hint,
        )
        for index, case in enumerate(fallback)
    )
    return (*tests, *remapped)[:count]


def _parse_scripts_payload(content: str) -> dict:
    """Парсит JSON; при обёртке tests на верхнем уровне нормализует."""
    data = parse_json_object(content)
    if "tests" in data:
        return data
    # Иногда модель кладёт сценарии в другой ключ.
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
        tests.append(
            BehaviorTestCase(
                id=test_id[:64],
                name=name[:120],
                stdin=stdin[:4000],
                expected_stdout=expected[:8000],
                expected_exit_code=exit_code,
                main_class_hint=hint,
            )
        )
    return tuple(tests)
