"""Оркестрация применения quick fix."""

from __future__ import annotations

from app.services.source_guard import ensure_java_source_size
from app.transform.apply_fix import AppliedFix, apply_quick_fix


def apply_fix_request(
    source: str,
    *,
    fix_id: str,
    expected_source_hash: str,
    expected_start_byte: int,
    expected_end_byte: int,
    expected_text: str,
    max_source_bytes: int,
) -> AppliedFix:
    ensure_java_source_size(source, max_source_bytes=max_source_bytes)
    return apply_quick_fix(
        source,
        fix_id,
        expected_source_hash,
        expected_start_byte,
        expected_end_byte,
        expected_text,
    )
