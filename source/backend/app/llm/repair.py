"""Исправление Java через LLM: полный файл или точечные replacements для крупных файлов."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.logging import log_activity
from app.llm.call_options import LlmCallOptions
from app.llm.client import LlmClientError, chat_completion
from app.llm.json_extract import parse_json_object
from app.llm.prompts import build_repair_messages, format_issues_for_repair, repair_chat_payload
from app.llm.response_normalize import normalize_repair_payload, self_tests_all_passed
from app.llm.source_pack import LlmSourcePack, prefer_repair_replacements
from app.llm.text_patch import apply_line_replacements

logger = logging.getLogger("app.llm")

_FENCE_RE = re.compile(r"^```(?:java)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)

_SELF_TEST_RETRY = (
    "SELF-TESTS предыдущего ответа содержали fail или отсутствовали. "
    "Исправь код и верни JSON, где ВСЕ self_tests имеют status=pass. "
    "Не вводи новых логических ошибок."
)


@dataclass(frozen=True, slots=True)
class RepairResult:
    status: str
    java_source: str | None
    fixed_issue_ids: tuple[str, ...]
    notes: tuple[str, ...]
    model: str | None
    error_reason: str | None = None
    self_tests: tuple[dict[str, str], ...] = ()


def repair_java_source(
    *,
    source_pack: LlmSourcePack,
    issues: list[dict[str, Any]],
    options: LlmCallOptions,
    static_summary: str = "",
    original_source: str | None = None,
) -> RepairResult:
    """Запрашивает у LLM исправления: полный java или replacements."""
    model = options.model
    provider = options.credentials.provider
    if not issues:
        return RepairResult(
            status="no_issues",
            java_source=None,
            fixed_issue_ids=(),
            notes=("Нет ошибок для исправления.",),
            model=model,
            error_reason="no_issues",
        )

    base_source = original_source if original_source is not None else ""
    prefer_repl = prefer_repair_replacements(source_pack) or len(base_source) > 48_000
    capped_issues = issues[:24]
    issues_payload = format_issues_for_repair(capped_issues)
    messages = build_repair_messages(
        source_payload=source_pack.payload_text,
        issues_payload=issues_payload,
        pack_mode=source_pack.mode,
        truncated=source_pack.truncated or len(issues) > len(capped_issues),
        static_summary=static_summary,
        prefer_replacements=prefer_repl,
    )
    # DeepSeek: до 8k completion; для полного файла крупнее - до 16k если модель позволяет.
    max_tokens = 8192 if prefer_repl else min(16_384, max(4_096, source_pack.original_chars // 3 + 2_000))
    payload = repair_chat_payload(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        provider=provider,
    )
    log_activity(
        "llm_repair_start",
        model=model,
        provider=provider,
        issue_count=len(issues),
        pack_chars=source_pack.payload_chars,
        pack_mode=source_pack.mode,
        truncated=source_pack.truncated,
        prefer_replacements=prefer_repl,
        line_count=source_pack.line_count,
    )
    try:
        content = chat_completion(
            credentials=options.credentials,
            base_url=options.base_url,
            oauth_url=options.oauth_url,
            payload=payload,
            timeout_seconds=options.timeout_seconds,
            verify_ssl=options.verify_ssl,
        )
        data = normalize_repair_payload(parse_json_object(content))
        if not self_tests_all_passed(data.get("self_tests") or []):
            log_activity("llm_repair_self_tests_retry")
            retry_messages = [
                *messages,
                {"role": "assistant", "content": content[:6000]},
                {"role": "user", "content": _SELF_TEST_RETRY},
            ]
            retry_payload = repair_chat_payload(
                model=model,
                messages=retry_messages,
                max_tokens=max_tokens,
                provider=provider,
            )
            content = chat_completion(
                credentials=options.credentials,
                base_url=options.base_url,
                oauth_url=options.oauth_url,
                payload=retry_payload,
                timeout_seconds=options.timeout_seconds,
                verify_ssl=options.verify_ssl,
            )
            data = normalize_repair_payload(parse_json_object(content))

        java_source = _resolve_java(data, base_source)
        if java_source is None or not java_source.strip():
            log_activity("llm_repair_empty_java")
            return RepairResult(
                status="invalid_response",
                java_source=None,
                fixed_issue_ids=(),
                notes=(),
                model=model,
                error_reason="empty_java",
            )
        fixed_ids = tuple(data.get("fixed_issue_ids") or ())
        notes = tuple(data.get("notes") or ())
        self_tests = tuple(data.get("self_tests") or ())
        if prefer_repl and data.get("replacements"):
            notes = (*notes, "applied_line_replacements")
        if not self_tests_all_passed(list(self_tests)):
            notes = (*notes, "self_tests_incomplete")
        log_activity(
            "llm_repair_ok",
            model=model,
            fixed_count=len(fixed_ids),
            java_chars=len(java_source),
            self_tests_pass=self_tests_all_passed(list(self_tests)),
        )
        return RepairResult(
            status="ok",
            java_source=java_source,
            fixed_issue_ids=fixed_ids,
            notes=notes,
            model=model,
            self_tests=self_tests,
        )
    except LlmClientError as exc:
        log_activity("llm_repair_unavailable", reason=exc.reason)
        return RepairResult(
            status="unavailable",
            java_source=None,
            fixed_issue_ids=(),
            notes=(),
            model=model,
            error_reason=exc.reason,
        )
    except (ValueError, TypeError, KeyError) as exc:
        logger.warning("llm_repair_invalid_response error=%s", type(exc).__name__)
        log_activity("llm_repair_invalid_response")
        return RepairResult(
            status="invalid_response",
            java_source=None,
            fixed_issue_ids=(),
            notes=(),
            model=model,
            error_reason="invalid_response",
        )


def _resolve_java(data: dict[str, Any], base_source: str) -> str | None:
    java_raw = data.get("java")
    if isinstance(java_raw, str) and java_raw.strip():
        return _normalize_java(java_raw)
    replacements = data.get("replacements")
    if isinstance(replacements, list) and replacements and base_source:
        patched = apply_line_replacements(base_source, replacements)
        if patched.strip() and patched != base_source:
            return patched if patched.endswith("\n") else patched + "\n"
    return None


def _normalize_java(text: str) -> str:
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip() + ("\n" if not match.group(1).endswith("\n") else "")
    if not stripped.endswith("\n"):
        stripped += "\n"
    return stripped
