"""Применение строковых replacements к исходному тексту (1-based inclusive lines)."""

from __future__ import annotations

from typing import Any


def apply_line_replacements(source: str, replacements: list[dict[str, Any]]) -> str:
    """Применяет замены снизу вверх, чтобы не сдвигать номера ещё не тронутых диапазонов."""
    if not replacements:
        return source
    lines = source.splitlines(keepends=True)
    # Нормализуем конец файла без финального \\n в splitlines(keepends).
    parsed: list[tuple[int, int, str]] = []
    for item in replacements:
        try:
            start = int(item["start_line"])
            end = int(item["end_line"])
        except (KeyError, TypeError, ValueError):
            continue
        replacement = item.get("replacement")
        if not isinstance(replacement, str) or start < 1 or end < start:
            continue
        parsed.append((start, end, replacement))
    if not parsed:
        return source

    parsed.sort(key=lambda row: row[0], reverse=True)
    for start, end, replacement in parsed:
        start_idx = start - 1
        end_idx = end
        if start_idx >= len(lines):
            continue
        end_idx = min(end_idx, len(lines))
        new_chunk = replacement
        if new_chunk and not new_chunk.endswith("\n"):
            new_chunk += "\n"
        new_lines = new_chunk.splitlines(keepends=True)
        lines[start_idx:end_idx] = new_lines
    result = "".join(lines)
    if source.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result
