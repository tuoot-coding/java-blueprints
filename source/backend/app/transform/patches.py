"""Непересекающиеся байтовые патчи исходника.

Патчи применяются от конца к началу, чтобы ранние смещения не съезжали.
Пересечение диапазонов - ошибка, а не тихое склеивание.
"""

from __future__ import annotations

from dataclasses import dataclass


class PatchApplyError(ValueError):
    """Патч выходит за исходник или пересекается с другим патчем."""


@dataclass(frozen=True, slots=True)
class SourcePatch:
    start_byte: int
    end_byte: int
    replacement: str


def apply_patches(source: str, patches: tuple[SourcePatch, ...] | list[SourcePatch]) -> str:
    """Применяет патчи к UTF-8 представлению и декодирует результат."""
    if not patches:
        return source
    source_bytes = bytearray(source.encode("utf-8"))
    ordered = sorted(patches, key=lambda patch: (patch.start_byte, patch.end_byte), reverse=True)
    next_start: int | None = None
    for patch in ordered:
        if (
            patch.start_byte < 0
            or patch.end_byte < patch.start_byte
            or patch.end_byte > len(source_bytes)
        ):
            raise PatchApplyError("патч выходит за границы исходника")
        if next_start is not None and patch.end_byte > next_start:
            raise PatchApplyError("диапазоны патчей пересекаются")
        replacement = patch.replacement.encode("utf-8")
        source_bytes[patch.start_byte : patch.end_byte] = replacement
        next_start = patch.start_byte
    return bytes(source_bytes).decode("utf-8")
