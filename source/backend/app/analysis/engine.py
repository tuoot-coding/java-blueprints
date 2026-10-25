"""Сборка статического анализа.

cfg_by_method необязателен. Правила недостижимости, пустых блоков и сложности
считаются по IR. Граф используется только как признак cfg_partial в метриках
метода и не добавляет ребер, которых нет в CFG.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.analysis.models import AnalysisDiagnostic, AnalysisMetrics
from app.analysis.rules.bloat import find_bloat
from app.analysis.rules.complexity import find_complexity, method_metrics
from app.analysis.rules.empty_blocks import find_empty_blocks
from app.analysis.rules.unreachable import find_unreachable
from app.analysis.rules.unsupported import find_unsupported
from app.graph.models import CfgGraph
from app.ir.models import IrNode
from app.ir.query import count_unsupported
from app.transform.quick_fixes import QuickFix, build_unreachable_fixes


@dataclass(frozen=True, slots=True)
class AnalysisRun:
    diagnostics: tuple[AnalysisDiagnostic, ...]
    quick_fixes: tuple[QuickFix, ...]
    metrics: AnalysisMetrics


def run_static_analysis(
    ir: IrNode,
    cfg_by_method: dict[str, CfgGraph] | None = None,
    *,
    source: str,
) -> AnalysisRun:
    """Запускает структурные правила и безопасные quick fix для недостижимого кода."""
    diagnostics = [
        *find_unreachable(ir),
        *find_empty_blocks(ir),
        *find_complexity(ir),
        *find_bloat(ir),
        *find_unsupported(ir),
    ]
    fixes = build_unreachable_fixes(source, diagnostics)
    fix_by_node = {fix.ir_node_id: fix.id for fix in fixes}
    linked = tuple(
        replace(item, quick_fix_id=fix_by_node.get(item.related_ir_ids[0]))
        if item.related_ir_ids and item.related_ir_ids[0] in fix_by_node
        else item
        for item in diagnostics
    )
    methods = method_metrics(ir, cfg_by_method)
    max_complexity = max((item.cyclomatic_complexity for item in methods), default=0)
    return AnalysisRun(
        diagnostics=linked,
        quick_fixes=fixes,
        metrics=AnalysisMetrics(
            methods=methods,
            max_cyclomatic_complexity=max_complexity,
            unsupported_count=count_unsupported(ir),
        ),
    )
