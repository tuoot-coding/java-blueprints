"""Подсказка по каждому непрозрачному узлу IR.

Дочерние узлы внутри unsupported не создаются, поэтому диагностика не дублируется
на внутренности среза.
"""

from __future__ import annotations

import re

from app.analysis.models import AnalysisDiagnostic, AnalysisSeverity
from app.ir.models import IrNode, IrNodeKind
from app.ir.query import walk_ir
from app.texts.analysis import AnalysisRule, analysis_explanation, unsupported_message

_REASON = re.compile(r"^[A-Za-z0-9_]{1,80}$")


def find_unsupported(root: IrNode) -> tuple[AnalysisDiagnostic, ...]:
    diagnostics: list[AnalysisDiagnostic] = []
    for node in walk_ir(root):
        if node.kind != IrNodeKind.UNSUPPORTED:
            continue
        reason = node.reason if node.reason and _REASON.fullmatch(node.reason) else "unknown"
        diagnostics.append(
            AnalysisDiagnostic(
                severity=AnalysisSeverity.INFO,
                rule_id=AnalysisRule.UNSUPPORTED,
                message=unsupported_message(reason),
                explanation=analysis_explanation(AnalysisRule.UNSUPPORTED),
                span=node.span,
                related_ir_ids=(node.id,),
            )
        )
    return tuple(diagnostics)
