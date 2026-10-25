"""Рекурсивная генерация Java по модульной логической схеме через GigaChat."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.core.logging import log_activity
from app.llm.call_options import LlmCallOptions
from app.llm.client import LlmClientError, chat_completion
from app.llm.json_extract import parse_json_object
from app.llm.prompts import build_scheme_to_code_messages, scheme_to_code_chat_payload
from app.structure.scratch import ScratchModule, ScratchProgram, serialize_scratch_outline

logger = logging.getLogger("app.llm")

_FENCE_RE = re.compile(r"^```(?:java)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SchemeCodegenResult:
    status: str
    java_source: str | None
    modules_written: tuple[str, ...]
    notes: tuple[str, ...]
    model: str | None
    error_reason: str | None = None


def generate_java_from_modular_scheme(
    *,
    program: ScratchProgram,
    source: str,
    options: LlmCallOptions,
) -> SchemeCodegenResult:
    """Генерирует код по схеме: обходит модули рекурсивно и собирает полный файл через LLM."""
    outline = serialize_scratch_outline(program)
    # Рекурсивный порядок: сначала корневые class-модули, затем вложенные method.
    module_order = _recursive_module_order(program.modules)
    focus_names = [module.name for module in module_order]
    log_activity(
        "llm_scheme_codegen_start",
        modules=len(module_order),
        blocks=len(program.blocks),
        model=options.model,
    )

    # Один вызов с полным деревом модулей в порядке DFS: модель обязана реализовать
    # каждый модуль рекурсивно; порядок передается явно в outline + focus list.
    ordered_outline = (
        outline + "\nMODULE_DFS_ORDER:\n" + "\n".join(f"- {name}" for name in focus_names)
    )
    messages = build_scheme_to_code_messages(
        scheme_outline=ordered_outline,
        source=source,
        module_focus=None,
    )
    max_tokens = min(16_384, max(4_096, len(source) // 3 + 2_000))
    payload = scheme_to_code_chat_payload(
        model=options.model,
        messages=messages,
        max_tokens=max_tokens,
        provider=options.credentials.provider,
    )
    try:
        content = chat_completion(
            credentials=options.credentials,
            base_url=options.base_url,
            oauth_url=options.oauth_url,
            payload=payload,
            timeout_seconds=options.timeout_seconds,
            verify_ssl=options.verify_ssl,
            http_referer="http://localhost:3000",
            app_title="Java Blueprints",
        )
        data = parse_json_object(content)
        java_raw = data.get("java")
        if not isinstance(java_raw, str) or not java_raw.strip():
            return SchemeCodegenResult(
                status="invalid_response",
                java_source=None,
                modules_written=(),
                notes=(),
                model=options.model,
                error_reason="empty_java",
            )
        modules_raw = data.get("modules_written", [])
        modules_written = (
            tuple(str(item) for item in modules_raw if str(item).strip())
            if isinstance(modules_raw, list)
            else tuple(focus_names)
        )
        notes_raw = data.get("notes", [])
        notes = tuple(str(item) for item in notes_raw) if isinstance(notes_raw, list) else ()
        java_source = _normalize_java(java_raw)
        log_activity(
            "llm_scheme_codegen_ok",
            modules_written=len(modules_written),
            java_chars=len(java_source),
        )
        return SchemeCodegenResult(
            status="ok",
            java_source=java_source,
            modules_written=modules_written,
            notes=notes,
            model=options.model,
        )
    except LlmClientError as exc:
        log_activity("llm_scheme_codegen_unavailable", reason=exc.reason)
        return SchemeCodegenResult(
            status="unavailable",
            java_source=None,
            modules_written=(),
            notes=(),
            model=options.model,
            error_reason=exc.reason,
        )
    except (ValueError, TypeError, KeyError) as exc:
        logger.warning("llm_scheme_codegen_invalid error=%s", type(exc).__name__)
        return SchemeCodegenResult(
            status="invalid_response",
            java_source=None,
            modules_written=(),
            notes=(),
            model=options.model,
            error_reason="invalid_response",
        )


def _recursive_module_order(modules: tuple[ScratchModule, ...]) -> list[ScratchModule]:
    """DFS: корневые модули, затем дочерние по parent_module_id."""
    by_parent: dict[str | None, list[ScratchModule]] = {}
    for module in modules:
        by_parent.setdefault(module.parent_module_id, []).append(module)
    ordered: list[ScratchModule] = []

    def visit(parent_id: str | None) -> None:
        for child in by_parent.get(parent_id, []):
            ordered.append(child)
            visit(child.id)

    visit(None)
    # На случай циклов/осиротевших узлов.
    seen = {item.id for item in ordered}
    for module in modules:
        if module.id not in seen:
            ordered.append(module)
    return ordered


def _normalize_java(text: str) -> str:
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip() + ("\n" if not match.group(1).endswith("\n") else "")
    if not stripped.endswith("\n"):
        stripped += "\n"
    return stripped
