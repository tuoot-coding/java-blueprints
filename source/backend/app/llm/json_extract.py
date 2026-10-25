"""Извлечение и нормализация JSON-объекта из ответа модели."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger("app.llm")

_FENCE_RE = re.compile(r"^```(?:json|javascript)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)


def parse_json_object(raw: str) -> dict[str, Any]:
    """Достаёт JSON-объект из сырого ответа (fence, преамбула, усечение)."""
    text = _sanitize_json_text(_strip_fence(raw.strip()))
    candidates = [
        text,
        _extract_balanced_object(text),
        _repair_truncated_object(text),
        _strip_trailing_commas(text),
    ]
    last_error: Exception | None = None
    for candidate in candidates:
        if not candidate:
            continue
        cleaned = _strip_trailing_commas(candidate)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(data, dict):
            return data
        # Иногда модель возвращает массив тестов без обёртки.
        if isinstance(data, list):
            return {"tests": data, "notes": ["unwrapped_array"]}
        last_error = ValueError("ожидался JSON-объект")
    preview = text[:240].replace("\n", "\\n")
    logger.warning(
        "llm_json_parse_failed chars=%s preview=%s",
        len(text),
        preview,
    )
    if last_error is not None:
        raise last_error
    raise ValueError("ожидался JSON-объект")


def _sanitize_json_text(text: str) -> str:
    """Убирает BOM и «умные» кавычки, мешающие json.loads."""
    cleaned = text.lstrip("\ufeff").strip()
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    return cleaned


def _strip_trailing_commas(text: str) -> str:
    """Удаляет висящие запятые перед } и ] (частый дефект LLM JSON)."""
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _strip_fence(text: str) -> str:
    match = _FENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def _extract_balanced_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    # Объект не закрыт - вернём срез для попытки repair.
    return text[start:]


def _repair_truncated_object(text: str) -> str | None:
    """Закрывает оборванный JSON (типичный обрыв max_tokens) минимально валидно."""
    fragment = _extract_balanced_object(text) or text
    start = fragment.find("{")
    if start < 0:
        return None
    body = fragment[start:]
    # Убираем висящую запятую перед обрывом.
    body = re.sub(r",\s*$", "", body.rstrip())
    opens = body.count("{") - body.count("}")
    open_brackets = body.count("[") - body.count("]")
    # Незакрытая строка.
    if body.count('"') % 2 == 1:
        body += '"'
    body += "]" * max(0, open_brackets)
    body += "}" * max(0, opens)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    return body if isinstance(data, dict) else None
