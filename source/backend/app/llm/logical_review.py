"""Логический анализ Java через LLM с разбором строгого JSON-ответа."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.core.logging import log_activity
from app.llm.call_options import LlmCallOptions
from app.llm.client import LlmClientError, chat_completion
from app.llm.json_extract import parse_json_object
from app.llm.prompts import (
    build_logical_review_messages,
    build_review_verify_messages,
    format_issues_for_repair,
    llm_chat_payload,
    review_chat_payload,
)
from app.llm.response_normalize import normalize_review_payload
from app.llm.source_pack import LlmSourcePack
from app.parser.positions import LineIndex

logger = logging.getLogger("app.llm")

_JSON_RETRY_USER = (
    "Предыдущий ответ не был валидным JSON-объектом. "
    "Верни ТОЛЬКО один JSON-объект вида "
    '{"issues":[...],"notes":[...]} без markdown и без текста вокруг.'
)

# Пояснение явно снимает статус ошибки - локальный фильтр до/после verify.
_FALSE_POSITIVE_MARKERS = (
    "не является ошибкой",
    "не ошибка",
    "не баг",
    "не является багом",
    "ложное срабатывание",
    "ложная ошибка",
    "false positive",
    "not a bug",
    "not an error",
    "это не ошибка",
    "ошибкой не является",
    "допустимое поведение",
    "не дефект",
)


@dataclass(frozen=True, slots=True)
class LlmSuggestedFix:
    title: str
    replacement: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    start_byte: int
    end_byte: int
    expected_snippet: str
    auto_applicable: bool


@dataclass(frozen=True, slots=True)
class LlmLogicalIssue:
    id: str
    severity: str
    code: str
    title: str
    message: str
    explanation: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    start_byte: int
    end_byte: int
    confidence: str
    fix: LlmSuggestedFix | None
    affects_execution: bool = True


@dataclass(frozen=True, slots=True)
class LogicalReviewResult:
    status: str
    issues: tuple[LlmLogicalIssue, ...]
    notes: tuple[str, ...]
    model: str | None
    error_reason: str | None = None


def review_java_logic(
    *,
    source: str,
    source_pack: LlmSourcePack,
    syntax_summary: str,
    options: LlmCallOptions,
) -> LogicalReviewResult:
    model = options.model
    provider = options.credentials.provider
    messages = build_logical_review_messages(
        source_payload=source_pack.payload_text,
        syntax_summary=syntax_summary,
        pack_mode=source_pack.mode,
        truncated=source_pack.truncated,
    )
    # Много issues на крупных файлах - иначе JSON обрывается (invalid_response).
    max_tokens = min(8192, max(3500, source_pack.control_nodes * 80 + 2000))
    payload = review_chat_payload(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        provider=provider,
    )
    log_activity(
        "llm_logical_review_start",
        model=model,
        provider=provider,
        source_chars=source_pack.original_chars,
        pack_chars=source_pack.payload_chars,
        pack_mode=source_pack.mode,
        truncated=source_pack.truncated,
        max_tokens=max_tokens,
    )
    line_index = LineIndex(source, source.encode("utf-8"))
    try:
        content = chat_completion(
            credentials=options.credentials,
            base_url=options.base_url,
            oauth_url=options.oauth_url,
            payload=payload,
            timeout_seconds=options.timeout_seconds,
            verify_ssl=options.verify_ssl,
        )
        data = _parse_review_content(
            content, options=options, messages=messages, max_tokens=max_tokens
        )
        normalized = normalize_review_payload(data)
        issues = tuple(
            _parse_issue(item, index, line_index, source)
            for index, item in enumerate(normalized["issues"])
            if isinstance(item, dict)
        )
        notes = list(normalized["notes"])
        before_local = len(issues)
        issues, dropped_local = _drop_false_positives_local(issues)
        if dropped_local:
            notes.append(f"false_positive_local_dropped={dropped_local}")
        if issues:
            issues, verify_notes = _verify_issues_with_llm(
                issues=issues,
                source_pack=source_pack,
                options=options,
            )
            notes.extend(verify_notes)
        log_activity(
            "llm_logical_review_ok",
            model=model,
            issue_count=len(issues),
            before_filter=before_local,
            fixable_count=sum(1 for item in issues if item.fix is not None),
        )
        return LogicalReviewResult(
            status="ok",
            issues=issues,
            notes=tuple(notes),
            model=model,
        )
    except LlmClientError as exc:
        log_activity("llm_logical_review_unavailable", reason=exc.reason)
        return LogicalReviewResult(
            status="unavailable",
            issues=(),
            notes=(),
            model=model,
            error_reason=exc.reason,
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        logger.warning(
            "llm_logical_review_invalid_response error=%s",
            type(exc).__name__,
        )
        log_activity("llm_logical_review_invalid_response", error=type(exc).__name__)
        return LogicalReviewResult(
            status="invalid_response",
            issues=(),
            notes=(),
            model=model,
            error_reason="invalid_response",
        )


def _parse_review_content(
    content: str,
    *,
    options: LlmCallOptions,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> dict[str, Any]:
    try:
        return parse_json_object(content)
    except (ValueError, TypeError) as first_error:
        # Один повтор с жёстким требованием JSON.
        retry_messages = [
            *messages,
            {"role": "assistant", "content": content[:4000]},
            {"role": "user", "content": _JSON_RETRY_USER},
        ]
        retry_payload = review_chat_payload(
            model=options.model,
            messages=retry_messages,
            max_tokens=min(4096, max_tokens),
            provider=options.credentials.provider,
        )
        log_activity("llm_logical_review_json_retry")
        try:
            retry_content = chat_completion(
                credentials=options.credentials,
                base_url=options.base_url,
                oauth_url=options.oauth_url,
                payload=retry_payload,
                timeout_seconds=min(90.0, options.timeout_seconds),
                verify_ssl=options.verify_ssl,
            )
            return parse_json_object(retry_content)
        except LlmClientError:
            raise first_error from first_error
        except (ValueError, TypeError):
            raise first_error from first_error


def _parse_issue(
    item: dict[str, Any],
    index: int,
    line_index: LineIndex,
    source: str,
) -> LlmLogicalIssue:
    severity = str(item.get("severity", "warning"))
    if severity not in {"error", "warning", "info", "hint", "structure"}:
        severity = "warning"
    confidence = str(item.get("confidence", "medium"))
    if confidence not in {"high", "medium"}:
        confidence = "medium"
    start_line = max(1, int(item.get("start_line", 1)))
    start_column = max(1, int(item.get("start_column", 1)))
    end_line = max(start_line, int(item.get("end_line", start_line)))
    end_column = max(1, int(item.get("end_column", start_column + 1)))
    start_byte = line_index.line_utf16_column_to_byte(start_line, start_column)
    end_byte = line_index.line_utf16_column_to_byte(end_line, end_column)
    code = str(item.get("code", "llm.logic.issue"))
    if not code.startswith("llm."):
        code = f"llm.logic.{code}"
    affects_raw = item.get("affects_execution")
    if isinstance(affects_raw, bool):
        affects_execution = affects_raw
    elif severity in {"info", "hint", "structure"} or code.startswith(
        ("llm.structure.", "llm.bloat.", "llm.complexity.")
    ):
        affects_execution = False
    else:
        affects_execution = True
    if not affects_execution and severity in {"error", "warning"}:
        severity = (
            "structure"
            if code.startswith(("llm.structure.", "llm.bloat."))
            else "info"
        )
    issue_id = str(item.get("id") or f"issue_{index + 1}")
    fix_raw = item.get("fix")
    fix = None
    if isinstance(fix_raw, dict) and affects_execution:
        fix = _parse_fix(fix_raw, line_index, source)
    return LlmLogicalIssue(
        id=issue_id,
        severity=severity,
        code=code,
        title=str(item.get("title", "Логическая проблема")),
        message=str(item.get("message", "")),
        explanation=str(item.get("explanation", "")),
        start_line=start_line,
        start_column=start_column,
        end_line=end_line,
        end_column=end_column,
        start_byte=start_byte,
        end_byte=end_byte,
        confidence=confidence,
        fix=fix,
        affects_execution=affects_execution,
    )


def _drop_false_positives_local(
    issues: tuple[LlmLogicalIssue, ...],
) -> tuple[tuple[LlmLogicalIssue, ...], int]:
    """Убирает issues, чьё пояснение само отрицает наличие ошибки."""
    kept: list[LlmLogicalIssue] = []
    dropped = 0
    for issue in issues:
        blob = f"{issue.explanation} {issue.message} {issue.title}".lower()
        if any(marker in blob for marker in _FALSE_POSITIVE_MARKERS):
            dropped += 1
            continue
        kept.append(issue)
    return tuple(kept), dropped


def _verify_issues_with_llm(
    *,
    issues: tuple[LlmLogicalIssue, ...],
    source_pack: LlmSourcePack,
    options: LlmCallOptions,
) -> tuple[tuple[LlmLogicalIssue, ...], list[str]]:
    """Повторный проход: LLM отмечает ложные id, их не отдаём пользователю."""
    if not issues:
        return issues, []
    issues_payload = format_issues_for_repair(
        [
            {
                "id": issue.id,
                "severity": issue.severity,
                "code": issue.code,
                "title": issue.title,
                "message": issue.message,
                "explanation": issue.explanation,
                "start_line": issue.start_line,
                "end_line": issue.end_line,
            }
            for issue in issues
        ]
    )
    # Добавим explanation в компактный вид - format_issues не включает explanation.
    enriched_lines = [
        f"{line} | expl={(issue.explanation or '')[:180]}"
        for line, issue in zip(issues_payload.splitlines(), issues, strict=False)
    ]
    messages = build_review_verify_messages(
        source_payload=source_pack.payload_text,
        issues_payload="\n".join(enriched_lines) if enriched_lines else issues_payload,
    )
    payload = llm_chat_payload(
        model=options.model,
        messages=messages,
        schema={
            "type": "object",
            "properties": {
                "keep_ids": {"type": "array", "items": {"type": "string"}},
                "drop_ids": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["keep_ids", "drop_ids", "notes"],
        },
        temperature=0.0,
        max_tokens=2048,
        provider=options.credentials.provider,
    )
    log_activity("llm_logical_review_verify_start", issue_count=len(issues))
    try:
        content = chat_completion(
            credentials=options.credentials,
            base_url=options.base_url,
            oauth_url=options.oauth_url,
            payload=payload,
            timeout_seconds=min(90.0, options.timeout_seconds),
            verify_ssl=options.verify_ssl,
        )
        data = parse_json_object(content)
    except (LlmClientError, ValueError, TypeError, json.JSONDecodeError) as exc:
        log_activity("llm_logical_review_verify_skipped", reason=type(exc).__name__)
        return issues, [f"verify_skipped:{type(exc).__name__}"]

    drop_raw = data.get("drop_ids") if isinstance(data, dict) else None
    keep_raw = data.get("keep_ids") if isinstance(data, dict) else None
    drop_ids = {
        str(item).strip()
        for item in (drop_raw if isinstance(drop_raw, list) else [])
        if str(item).strip()
    }
    keep_ids = {
        str(item).strip()
        for item in (keep_raw if isinstance(keep_raw, list) else [])
        if str(item).strip()
    }
    # Если модель вернула keep - уважаем его; иначе вычитаем только drop.
    if keep_ids:
        kept = tuple(issue for issue in issues if issue.id in keep_ids and issue.id not in drop_ids)
    else:
        kept = tuple(issue for issue in issues if issue.id not in drop_ids)
    # Повторный локальный фильтр на случай, если verify оставил сомнительные.
    kept, extra_local = _drop_false_positives_local(kept)
    dropped = len(issues) - len(kept)
    notes = [f"false_positive_verify_dropped={dropped}"]
    if extra_local:
        notes.append(f"false_positive_verify_local_extra={extra_local}")
    verify_notes_raw = data.get("notes") if isinstance(data, dict) else None
    if isinstance(verify_notes_raw, list):
        notes.extend(str(item) for item in verify_notes_raw[:5])
    log_activity(
        "llm_logical_review_verify_ok",
        kept=len(kept),
        dropped=dropped,
    )
    return kept, notes


def _parse_fix(
    item: dict[str, Any],
    line_index: LineIndex,
    source: str,
) -> LlmSuggestedFix | None:
    replacement = item.get("replacement")
    if not isinstance(replacement, str):
        return None
    start_line = max(1, int(item.get("start_line", 1)))
    start_column = max(1, int(item.get("start_column", 1)))
    end_line = max(start_line, int(item.get("end_line", start_line)))
    end_column = max(1, int(item.get("end_column", start_column + 1)))
    start_byte = line_index.line_utf16_column_to_byte(start_line, start_column)
    end_byte = line_index.line_utf16_column_to_byte(end_line, end_column)
    source_bytes = source.encode("utf-8")
    if start_byte < 0 or end_byte < start_byte or end_byte > len(source_bytes):
        return None
    current = source_bytes[start_byte:end_byte].decode("utf-8")
    expected = item.get("expected_snippet")
    expected_snippet = current if not isinstance(expected, str) or not expected else expected
    auto = item.get("auto_applicable", True)
    return LlmSuggestedFix(
        title=str(item.get("title", "Применить исправление")),
        replacement=replacement,
        start_line=start_line,
        start_column=start_column,
        end_line=end_line,
        end_column=end_column,
        start_byte=start_byte,
        end_byte=end_byte,
        expected_snippet=expected_snippet,
        auto_applicable=bool(auto),
    )
