"""Применение quick fix с проверкой отпечатка и повторным разбором.

Правка применяется только если заново посчитанный fix совпал с fix_id,
диапазоном и ожидаемым текстом. Произвольный диапазон клиента не исполняется.
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus

from app.analysis.engine import run_static_analysis
from app.core.errors import ApplicationError
from app.ir.builder import build_structural_ir
from app.parser.models import JavaParseResult
from app.parser.service import inspect_java_source, parse_java_source
from app.schemas.errors import ErrorCode
from app.transform.fingerprint import source_fingerprint
from app.transform.patches import PatchApplyError, SourcePatch, apply_patches


@dataclass(frozen=True, slots=True)
class AppliedFix:
    source: str
    source_hash: str
    fix_id: str
    parse_result: JavaParseResult


def apply_quick_fix(
    source: str,
    fix_id: str,
    expected_source_hash: str,
    expected_start_byte: int,
    expected_end_byte: int,
    expected_text: str,
) -> AppliedFix:
    """Проверяет отпечаток, применяет совпавший fix и заново парсит результат."""
    actual_hash = source_fingerprint(source)
    if actual_hash != expected_source_hash:
        raise ApplicationError(
            ErrorCode.FIX_NOT_APPLICABLE,
            status_code=HTTPStatus.CONFLICT,
            details={"reason": "source_hash_mismatch"},
        )
    inspection = inspect_java_source(source)
    ir = build_structural_ir(source, inspection.tree)
    analysis = run_static_analysis(ir, source=source)
    matched = next((item for item in analysis.quick_fixes if item.id == fix_id), None)
    if matched is None:
        raise _not_applicable("unknown_fix")
    if (
        matched.start_byte != expected_start_byte
        or matched.end_byte != expected_end_byte
        or matched.expected_text != expected_text
        or matched.replacement != ""
    ):
        raise _not_applicable("fix_mismatch")
    source_bytes = source.encode("utf-8")
    if expected_end_byte > len(source_bytes) or expected_start_byte < 0:
        raise _not_applicable("range_mismatch")
    try:
        actual_text = source_bytes[expected_start_byte:expected_end_byte].decode("utf-8")
    except UnicodeDecodeError as error:
        raise _not_applicable("range_mismatch") from error
    if actual_text != expected_text:
        raise _not_applicable("text_mismatch")
    try:
        updated = apply_patches(
            source,
            [SourcePatch(expected_start_byte, expected_end_byte, "")],
        )
    except PatchApplyError as error:
        raise _not_applicable("patch_rejected") from error
    return AppliedFix(
        source=updated,
        source_hash=source_fingerprint(updated),
        fix_id=fix_id,
        parse_result=parse_java_source(updated),
    )


def _not_applicable(reason: str) -> ApplicationError:
    return ApplicationError(
        ErrorCode.FIX_NOT_APPLICABLE,
        status_code=HTTPStatus.CONFLICT,
        details={"reason": reason},
    )
