"""Сравнение двух модульных логических схем."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.structure.scratch import ScratchProgram, serialize_scratch_outline


@dataclass(frozen=True, slots=True)
class SchemeCompareResult:
    """Сравнительная характеристика исходной и новой логической схемы."""

    original_block_count: int
    generated_block_count: int
    original_module_count: int
    generated_module_count: int
    original_method_names: tuple[str, ...]
    generated_method_names: tuple[str, ...]
    methods_added: tuple[str, ...]
    methods_removed: tuple[str, ...]
    kinds_original: dict[str, int]
    kinds_generated: dict[str, int]
    kinds_delta: dict[str, int]
    structural_similarity: float
    outline_original: str
    outline_generated: str
    changed: bool
    report_lines: tuple[str, ...]


def compare_scratch_programs(
    original: ScratchProgram,
    generated: ScratchProgram,
) -> SchemeCompareResult:
    """Сравнивает модульный состав и виды блоков двух схем."""
    kinds_orig = _kind_counts(original)
    kinds_gen = _kind_counts(generated)
    all_kinds = sorted(set(kinds_orig) | set(kinds_gen))
    kinds_delta = {kind: kinds_gen.get(kind, 0) - kinds_orig.get(kind, 0) for kind in all_kinds}

    orig_methods = set(original.method_names)
    gen_methods = set(generated.method_names)
    added = tuple(sorted(gen_methods - orig_methods))
    removed = tuple(sorted(orig_methods - gen_methods))

    similarity = _structural_similarity(kinds_orig, kinds_gen, orig_methods, gen_methods)
    outline_original = serialize_scratch_outline(original)
    outline_generated = serialize_scratch_outline(generated)
    changed = outline_original != outline_generated

    report = (
        f"blocks {len(original.blocks)}->{len(generated.blocks)}",
        f"modules {len(original.modules)}->{len(generated.modules)}",
        f"methods {len(orig_methods)}->{len(gen_methods)} "
        f"added={list(added)} removed={list(removed)}",
        f"structural_similarity={similarity:.3f} changed={changed}",
        f"kinds_delta={kinds_delta}",
    )
    return SchemeCompareResult(
        original_block_count=len(original.blocks),
        generated_block_count=len(generated.blocks),
        original_module_count=len(original.modules),
        generated_module_count=len(generated.modules),
        original_method_names=tuple(original.method_names),
        generated_method_names=tuple(generated.method_names),
        methods_added=added,
        methods_removed=removed,
        kinds_original=dict(kinds_orig),
        kinds_generated=dict(kinds_gen),
        kinds_delta=kinds_delta,
        structural_similarity=similarity,
        outline_original=outline_original,
        outline_generated=outline_generated,
        changed=changed,
        report_lines=report,
    )


def _kind_counts(program: ScratchProgram) -> dict[str, int]:
    return dict(Counter(block.kind for block in program.blocks))


def _structural_similarity(
    kinds_orig: dict[str, int],
    kinds_gen: dict[str, int],
    methods_orig: set[str],
    methods_gen: set[str],
) -> float:
    """Грубая оценка 0..1: пересечение видов блоков и сохранение методов."""
    keys = set(kinds_orig) | set(kinds_gen)
    if not keys and not methods_orig and not methods_gen:
        return 1.0
    kind_score = 0.0
    if keys:
        overlap = sum(min(kinds_orig.get(k, 0), kinds_gen.get(k, 0)) for k in keys)
        total = sum(max(kinds_orig.get(k, 0), kinds_gen.get(k, 0)) for k in keys)
        kind_score = overlap / total if total else 1.0
    method_score = 0.0
    union = methods_orig | methods_gen
    method_score = len(methods_orig & methods_gen) / len(union) if union else 1.0
    return round(0.6 * kind_score + 0.4 * method_score, 3)
