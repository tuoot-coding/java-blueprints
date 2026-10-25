"""Сравнение исходного и сгенерированного Java: метрики соответствия и времени."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.analysis.engine import run_static_analysis
from app.analysis.rules.bloat import find_bloat
from app.graph.builder import build_method_cfg
from app.ir.builder import build_structural_ir
from app.ir.query import list_methods, summarize_ir
from app.parser.service import inspect_java_source
from app.texts.analysis import AnalysisRule
from app.transform.fingerprint import source_fingerprint


@dataclass(frozen=True, slots=True)
class CodeCompareMetrics:
    """Показатели соответствия сгенерированного кода исходному."""

    elapsed_ms: float
    original_parse_ok: bool
    generated_parse_ok: bool
    class_names_match: bool
    public_methods_preserved: bool
    method_count_original: int
    method_count_generated: int
    method_count_delta: int
    line_count_original: int
    line_count_generated: int
    line_ratio: float
    max_method_lines_original: int
    max_method_lines_generated: int
    long_method_issues_original: int
    long_method_issues_generated: int
    duplicate_logic_original: int
    duplicate_logic_generated: int
    max_cyclomatic_original: int
    max_cyclomatic_generated: int
    source_changed: bool
    unsupported_original: int
    unsupported_generated: int
    score: float
    passed: bool
    report_lines: tuple[str, ...]


def compare_generated_to_original(original: str, generated: str) -> CodeCompareMetrics:
    """Сравнивает два Java-исходника структурно и по метрикам излишеств."""
    started = time.perf_counter()
    orig = _snapshot(original)
    gen = _snapshot(generated)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    class_match = orig.class_names == gen.class_names
    methods_preserved = orig.method_names.issubset(gen.method_names) or (
        not orig.method_names and not gen.method_names
    )
    line_ratio = (
        gen.line_count / orig.line_count if orig.line_count > 0 else (1.0 if gen.line_count == 0 else 0.0)
    )
    source_changed = source_fingerprint(original) != source_fingerprint(generated)

    # Балл 0..1: parse, API, улучшение/неухудшение bloat, разумный размер.
    score = 0.0
    if orig.parse_ok and gen.parse_ok:
        score += 0.35
    if class_match:
        score += 0.15
    if methods_preserved:
        score += 0.20
    if gen.long_method_issues <= orig.long_method_issues:
        score += 0.10
    if gen.duplicate_logic <= orig.duplicate_logic:
        score += 0.10
    if gen.max_method_lines <= orig.max_method_lines or gen.method_count >= orig.method_count:
        score += 0.10

    passed = (
        orig.parse_ok
        and gen.parse_ok
        and class_match
        and methods_preserved
        and gen.long_method_issues <= orig.long_method_issues
        and gen.duplicate_logic <= orig.duplicate_logic
        and score >= 0.75
    )

    report = (
        f"elapsed_ms={elapsed_ms:.2f}",
        f"parse_ok original={orig.parse_ok} generated={gen.parse_ok}",
        f"classes_match={class_match} methods_preserved={methods_preserved}",
        f"methods {orig.method_count}->{gen.method_count} (delta={gen.method_count - orig.method_count})",
        f"lines {orig.line_count}->{gen.line_count} (ratio={line_ratio:.3f})",
        f"max_method_lines {orig.max_method_lines}->{gen.max_method_lines}",
        f"long_method_issues {orig.long_method_issues}->{gen.long_method_issues}",
        f"duplicate_logic {orig.duplicate_logic}->{gen.duplicate_logic}",
        f"max_cyclomatic {orig.max_cyclomatic}->{gen.max_cyclomatic}",
        f"unsupported {orig.unsupported}->{gen.unsupported}",
        f"source_changed={source_changed} score={score:.3f} passed={passed}",
    )
    return CodeCompareMetrics(
        elapsed_ms=elapsed_ms,
        original_parse_ok=orig.parse_ok,
        generated_parse_ok=gen.parse_ok,
        class_names_match=class_match,
        public_methods_preserved=methods_preserved,
        method_count_original=orig.method_count,
        method_count_generated=gen.method_count,
        method_count_delta=gen.method_count - orig.method_count,
        line_count_original=orig.line_count,
        line_count_generated=gen.line_count,
        line_ratio=line_ratio,
        max_method_lines_original=orig.max_method_lines,
        max_method_lines_generated=gen.max_method_lines,
        long_method_issues_original=orig.long_method_issues,
        long_method_issues_generated=gen.long_method_issues,
        duplicate_logic_original=orig.duplicate_logic,
        duplicate_logic_generated=gen.duplicate_logic,
        max_cyclomatic_original=orig.max_cyclomatic,
        max_cyclomatic_generated=gen.max_cyclomatic,
        source_changed=source_changed,
        unsupported_original=orig.unsupported,
        unsupported_generated=gen.unsupported,
        score=score,
        passed=passed,
        report_lines=report,
    )


def format_compare_report(metrics: CodeCompareMetrics, *, title: str) -> str:
    lines = [f"=== {title} ===", *metrics.report_lines]
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class _Snapshot:
    parse_ok: bool
    class_names: tuple[str, ...]
    method_names: frozenset[str]
    method_count: int
    line_count: int
    max_method_lines: int
    long_method_issues: int
    duplicate_logic: int
    max_cyclomatic: int
    unsupported: int


def _snapshot(source: str) -> _Snapshot:
    inspection = inspect_java_source(source)
    parse_ok = not inspection.result.has_syntax_errors
    ir = build_structural_ir(source, inspection.tree)
    summary = summarize_ir(ir)
    methods = list_methods(ir)
    graphs = {method.id: build_method_cfg(method) for method in methods}
    analysis = run_static_analysis(ir, graphs, source=source)
    bloat = find_bloat(ir)
    long_issues = sum(1 for item in bloat if item.rule_id == AnalysisRule.LONG_METHOD)
    dup_issues = sum(1 for item in bloat if item.rule_id == AnalysisRule.DUPLICATE_LOGIC)
    max_lines = 0
    for method in methods:
        max_lines = max(max_lines, method.span.end_line - method.span.start_line + 1)
    return _Snapshot(
        parse_ok=parse_ok,
        class_names=summary.class_names,
        method_names=frozenset(summary.method_names),
        method_count=len(methods),
        line_count=source.count("\n") + (1 if source and not source.endswith("\n") else 0),
        max_method_lines=max_lines,
        long_method_issues=long_issues,
        duplicate_logic=dup_issues,
        max_cyclomatic=analysis.metrics.max_cyclomatic_complexity,
        unsupported=summary.unsupported_count,
    )
