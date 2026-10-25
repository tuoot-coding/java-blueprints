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
from app.llm.prompts import build_logical_review_messages, review_chat_payload
from app.llm.response_normalize import normalize_review_payload
from app.llm.source_pack import LlmSourcePack
from app.parser.positions import LineIndex

logger = logging.getLogger("app.llm")

_JSON_RETRY_USER = (
    "Предыдущий ответ не был валидным JSON-объектом. "
    "Верни ТОЛЬКО один JSON-объект вида "
    '{"issues":[...],"notes":[...]} без markdown и без текста вокруг.'
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
        data = _parse_review_content(content, options=options, messages=messages, max_tokens=max_tokens)
        normalized = normalize_review_payload(data)
        issues = tuple(
            _parse_issue(item, index, line_index, source)
            for index, item in enumerate(normalized["issues"])
            if isinstance(item, dict)
        )
        notes = tuple(normalized["notes"])
        log_activity(
            "llm_logical_review_ok",
            model=model,
            issue_count=len(issues),
            fixable_count=sum(1 for item in issues if item.fix is not None),
        )
        return LogicalReviewResult(
            status="ok",
            issues=issues,
            notes=notes,
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
    if severity not in {"error", "warning", "info", "hint"}:
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
    elif severity in {"info", "hint"}:
        affects_execution = False
    elif code.startswith(("llm.structure.", "llm.bloat.", "llm.complexity.")):
        affects_execution = False
    else:
        affects_execution = True
    if not affects_execution and severity in {"error", "warning"}:
        severity = "info"
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
