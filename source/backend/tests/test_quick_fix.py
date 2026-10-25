from __future__ import annotations

import hashlib

import pytest

from app.analysis.engine import run_static_analysis
from app.core.errors import ApplicationError
from app.schemas.errors import ErrorCode
from app.transform.apply_fix import apply_quick_fix
from app.transform.patches import PatchApplyError, SourcePatch, apply_patches
from tests.java_fixtures import ir_from_source, read_java_fixture


def test_apply_patches_descending_and_adjacent() -> None:
    updated = apply_patches(
        "abcdef",
        [SourcePatch(0, 1, "X"), SourcePatch(3, 4, "Y")],
    )
    assert updated == "XbcYef"
    assert apply_patches("ab", [SourcePatch(0, 1, "Q"), SourcePatch(1, 2, "Z")]) == "QZ"


def test_apply_patches_rejects_overlap_and_out_of_range() -> None:
    with pytest.raises(PatchApplyError):
        apply_patches("abcdef", [SourcePatch(0, 3, "Q"), SourcePatch(2, 4, "Z")])
    with pytest.raises(PatchApplyError):
        apply_patches("ab", [SourcePatch(0, 3, "Q")])


def test_apply_quick_fix_removes_unreachable_statement() -> None:
    source = read_java_fixture("unreachable.java")
    run = run_static_analysis(ir_from_source(source), source=source)
    fix = run.quick_fixes[0]
    applied = apply_quick_fix(
        source,
        fix.id,
        hashlib.sha256(source.encode("utf-8")).hexdigest(),
        fix.start_byte,
        fix.end_byte,
        fix.expected_text,
    )
    assert "int x = 1;" not in applied.source
    assert "return;" in applied.source
    assert applied.parse_result.has_syntax_errors is False
    assert applied.source_hash != hashlib.sha256(source.encode("utf-8")).hexdigest()


def test_apply_quick_fix_rejects_stale_hash_and_unknown_id() -> None:
    source = read_java_fixture("unreachable.java")
    run = run_static_analysis(ir_from_source(source), source=source)
    fix = run.quick_fixes[0]
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    with pytest.raises(ApplicationError) as stale:
        apply_quick_fix(source, fix.id, "0" * 64, fix.start_byte, fix.end_byte, fix.expected_text)
    assert stale.value.error_code == ErrorCode.FIX_NOT_APPLICABLE
    assert stale.value.details == {"reason": "source_hash_mismatch"}

    with pytest.raises(ApplicationError) as unknown:
        apply_quick_fix(source, "remove_unreachable_0_1", digest, 0, 1, "x")
    assert unknown.value.details == {"reason": "unknown_fix"}


def test_apply_quick_fix_rejects_mismatched_range() -> None:
    source = read_java_fixture("unreachable.java")
    run = run_static_analysis(ir_from_source(source), source=source)
    fix = run.quick_fixes[0]
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    with pytest.raises(ApplicationError) as mismatch:
        apply_quick_fix(source, fix.id, digest, fix.start_byte, fix.end_byte, "other")
    assert mismatch.value.details == {"reason": "fix_mismatch"}
