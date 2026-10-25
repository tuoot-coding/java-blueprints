"""Применение точечного LLM-исправления логической ошибки."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus

from app.core.errors import ApplicationError
from app.core.logging import log_activity
from app.parser.service import parse_java_source
from app.schemas.errors import ErrorCode
from app.transform.fingerprint import source_fingerprint
from app.transform.patches import PatchApplyError, SourcePatch, apply_patches


@dataclass(frozen=True, slots=True)
class LogicFixApplyResult:
    source: str
    source_hash: str
    previous_source_hash: str
    issue_id: str
    has_syntax_errors: bool
    parse_diagnostic_count: int


def apply_logic_fix_request(
    *,
    source: str,
    source_hash: str,
    issue_id: str,
    start_byte: int,
    end_byte: int,
    expected_snippet: str,
    replacement: str,
    max_source_bytes: int,
) -> LogicFixApplyResult:
    source_bytes = source.encode("utf-8")
    if len(source_bytes) > max_source_bytes:
        raise ApplicationError(
            ErrorCode.PAYLOAD_TOO_LARGE,
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            details={
                "max_source_bytes": max_source_bytes,
                "actual_source_bytes": len(source_bytes),
            },
        )

    current_hash = source_fingerprint(source)
    log_activity(
        "logic_fix_apply_start",
        issue_id=issue_id,
        start_byte=start_byte,
        end_byte=end_byte,
        source_hash=current_hash[:16],
    )
    if current_hash != source_hash:
        log_activity("logic_fix_stale_source", expected=source_hash[:16], actual=current_hash[:16])
        raise ApplicationError(
            ErrorCode.REVISION_CONFLICT,
            status_code=HTTPStatus.CONFLICT,
            details={"expected_source_hash": source_hash, "actual_source_hash": current_hash},
        )

    if start_byte < 0 or end_byte < start_byte or end_byte > len(source_bytes):
        raise ApplicationError(
            ErrorCode.FIX_NOT_APPLICABLE,
            status_code=HTTPStatus.CONFLICT,
            details={"reason": "range_out_of_bounds", "issue_id": issue_id},
        )

    actual_snippet = source_bytes[start_byte:end_byte].decode("utf-8")
    if actual_snippet != expected_snippet:
        log_activity(
            "logic_fix_snippet_mismatch",
            issue_id=issue_id,
            expected_len=len(expected_snippet),
            actual_len=len(actual_snippet),
        )
        raise ApplicationError(
            ErrorCode.FIX_NOT_APPLICABLE,
            status_code=HTTPStatus.CONFLICT,
            details={"reason": "snippet_mismatch", "issue_id": issue_id},
        )

    try:
        updated = apply_patches(
            source,
            [SourcePatch(start_byte=start_byte, end_byte=end_byte, replacement=replacement)],
        )
    except PatchApplyError as exc:
        raise ApplicationError(
            ErrorCode.FIX_NOT_APPLICABLE,
            status_code=HTTPStatus.CONFLICT,
            details={"reason": "patch_failed", "issue_id": issue_id},
        ) from exc

    if len(updated.encode("utf-8")) > max_source_bytes:
        raise ApplicationError(
            ErrorCode.PAYLOAD_TOO_LARGE,
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            details={"max_source_bytes": max_source_bytes},
        )

    parse_result = parse_java_source(updated)
    new_hash = source_fingerprint(updated)
    log_activity(
        "logic_fix_apply_ok",
        issue_id=issue_id,
        new_source_hash=new_hash[:16],
        has_syntax_errors=parse_result.has_syntax_errors,
        diagnostics=len(parse_result.diagnostics),
    )
    return LogicFixApplyResult(
        source=updated,
        source_hash=new_hash,
        previous_source_hash=current_hash,
        issue_id=issue_id,
        has_syntax_errors=parse_result.has_syntax_errors,
        parse_diagnostic_count=len(parse_result.diagnostics),
    )
