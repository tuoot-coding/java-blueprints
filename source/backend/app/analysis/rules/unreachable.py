"""Недостижимые операторы внутри одного блока.

Правило структурное: оператор недостижим, только если предыдущий сосед в том же
блоке - return, throw, break или continue. if и цикл сами по себе поток не
обрывают, даже если в их ветке есть return.
"""

from __future__ import annotations

from app.analysis.models import AnalysisDiagnostic, AnalysisSeverity
from app.ir.models import IrNode, IrNodeKind
from app.ir.query import walk_ir
from app.texts.analysis import AnalysisRule, analysis_explanation, unreachable_message

_TERMINATORS = frozenset(
    {
        IrNodeKind.RETURN,
        IrNodeKind.THROW,
        IrNodeKind.BREAK,
        IrNodeKind.CONTINUE,
    }
)


def find_unreachable(root: IrNode) -> tuple[AnalysisDiagnostic, ...]:
    diagnostics: list[AnalysisDiagnostic] = []
    for node in walk_ir(root):
        if node.kind != IrNodeKind.BLOCK:
            continue
        terminated = False
        for child in node.children:
            if child.kind == IrNodeKind.COMMENT:
                continue
            if terminated:
                diagnostics.append(
                    AnalysisDiagnostic(
                        severity=AnalysisSeverity.WARNING,
                        rule_id=AnalysisRule.UNREACHABLE,
                        message=unreachable_message(),
                        explanation=analysis_explanation(AnalysisRule.UNREACHABLE),
                        span=child.span,
                        related_ir_ids=(child.id,),
                    )
                )
            if child.kind in _TERMINATORS:
                terminated = True
    return tuple(diagnostics)
