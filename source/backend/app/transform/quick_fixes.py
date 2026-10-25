"""Quick fix удаления недостижимого оператора.

Удаляется весь диапазон оператора. Если оператор занимает свою строку,
в диапазон входят хвостовые пробелы и один перевод строки. Чужой код на той же
строке не захватывается.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis.models import AnalysisDiagnostic
from app.texts.analysis import QUICK_FIX_REMOVE_UNREACHABLE, AnalysisRule


@dataclass(frozen=True, slots=True)
class QuickFix:
    id: str
    rule_id: str
    title: str
    ir_node_id: str
    start_byte: int
    end_byte: int
    replacement: str
    expected_text: str


def build_unreachable_fixes(
    source: str,
    diagnostics: list[AnalysisDiagnostic] | tuple[AnalysisDiagnostic, ...],
) -> tuple[QuickFix, ...]:
    """Строит удаления только для диагностики java.unreachable_statement."""
    source_bytes = source.encode("utf-8")
    fixes: list[QuickFix] = []
    seen: set[tuple[int, int]] = set()
    for diagnostic in diagnostics:
        if diagnostic.rule_id != AnalysisRule.UNREACHABLE:
            continue
        if not diagnostic.related_ir_ids:
            continue
        start_byte, end_byte = extend_statement_deletion(
            source_bytes,
            diagnostic.span.start_byte,
            diagnostic.span.end_byte,
        )
        key = (start_byte, end_byte)
        if key in seen:
            continue
        seen.add(key)
        try:
            expected_text = source_bytes[start_byte:end_byte].decode("utf-8")
        except UnicodeDecodeError:
            continue
        fixes.append(
            QuickFix(
                id=f"remove_unreachable_{start_byte}_{end_byte}",
                rule_id=AnalysisRule.UNREACHABLE.value,
                title=QUICK_FIX_REMOVE_UNREACHABLE,
                ir_node_id=diagnostic.related_ir_ids[0],
                start_byte=start_byte,
                end_byte=end_byte,
                replacement="",
                expected_text=expected_text,
            )
        )
    return tuple(fixes)


def extend_statement_deletion(source_bytes: bytes, start: int, end: int) -> tuple[int, int]:
    """Расширяет конец удаления на хвостовые пробелы и перевод строки своей строки."""
    if start < 0 or end < start or end > len(source_bytes):
        return start, end
    cursor = end
    while cursor < len(source_bytes) and source_bytes[cursor] in {0x20, 0x09}:
        cursor += 1
    line_start = source_bytes.rfind(b"\n", 0, start) + 1
    prefix = source_bytes[line_start:start]
    if prefix.strip(b" \t\r") == b"" and cursor < len(source_bytes):
        if (
            source_bytes[cursor] == 0x0D
            and cursor + 1 < len(source_bytes)
            and source_bytes[cursor + 1] == 0x0A
        ):
            cursor += 2
        elif source_bytes[cursor] == 0x0A:
            cursor += 1
    return start, cursor
