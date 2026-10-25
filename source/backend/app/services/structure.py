"""Оркестрация структурных блоков для HTTP."""

from __future__ import annotations

from dataclasses import dataclass

from app.ir.query import IrSummary, summarize_ir
from app.services.inspection import load_java
from app.structure.blocks import build_structural_blocks
from app.structure.models import StructuralBlock


@dataclass(frozen=True, slots=True)
class StructureBuildResult:
    blocks: tuple[StructuralBlock, ...]
    ir_summary: IrSummary
    unsupported_count: int
    source_hash: str
    has_syntax_errors: bool


def build_structure_request(source: str, *, max_source_bytes: int) -> StructureBuildResult:
    loaded = load_java(source, max_source_bytes=max_source_bytes)
    summary = summarize_ir(loaded.ir)
    return StructureBuildResult(
        blocks=build_structural_blocks(loaded.ir),
        ir_summary=summary,
        unsupported_count=summary.unsupported_count,
        source_hash=loaded.source_hash,
        has_syntax_errors=loaded.inspection.result.has_syntax_errors,
    )
