"""Цикломатическая сложность в стиле Маккейба по структурному IR.

Формула: 1 + число точек решения в методе.

Точка решения:
- if, while, do, classic for, enhanced for;
- каждый catch;
- каждый бинарный оператор && или ||, если он лежит внутри условия
  if, while, do или classic for (включая скобки вокруг условия).

Не считается:
- switch и другие непрозрачные узлы, потому что их тело не раскрыто
  (оценка тогда занижена, а не завышена);
- && и || вне условий, например в инициализаторе переменной;
- else сам по себе (решение уже посчитано на if).

Диагностика уровня info выпускается только при сложности не ниже порога.
Метрика метода возвращается всегда.
"""

from __future__ import annotations

from app.analysis.models import AnalysisDiagnostic, AnalysisSeverity, MethodMetric
from app.graph.models import CfgGraph
from app.ir.models import ROLE_CONDITION, IrNode, IrNodeKind
from app.ir.query import list_methods
from app.texts.analysis import AnalysisRule, analysis_explanation, complexity_message

COMPLEXITY_INFO_THRESHOLD = 10

_DECISION_KINDS = frozenset(
    {
        IrNodeKind.IF,
        IrNodeKind.WHILE,
        IrNodeKind.DO,
        IrNodeKind.FOR,
        IrNodeKind.ENHANCED_FOR,
        IrNodeKind.CATCH,
    }
)

_SHORT_CIRCUIT = frozenset({"&&", "||"})


def method_metrics(
    root: IrNode,
    cfg_by_method: dict[str, CfgGraph] | None = None,
) -> tuple[MethodMetric, ...]:
    metrics: list[MethodMetric] = []
    for method in list_methods(root):
        graph = None if cfg_by_method is None else cfg_by_method.get(method.id)
        metrics.append(
            MethodMetric(
                method_name=method.name or "",
                ir_node_id=method.id,
                cyclomatic_complexity=cyclomatic_complexity(method),
                cfg_partial=None if graph is None else graph.partial,
            )
        )
    return tuple(metrics)


def cyclomatic_complexity(method: IrNode) -> int:
    """Консервативная структурная оценка. Не утверждает точную семантику Java."""
    return 1 + _decision_points(method, in_condition=False)


def find_complexity(root: IrNode) -> tuple[AnalysisDiagnostic, ...]:
    diagnostics: list[AnalysisDiagnostic] = []
    for method in list_methods(root):
        value = cyclomatic_complexity(method)
        if value < COMPLEXITY_INFO_THRESHOLD:
            continue
        name = method.name or "без имени"
        diagnostics.append(
            AnalysisDiagnostic(
                severity=AnalysisSeverity.INFO,
                rule_id=AnalysisRule.COMPLEXITY,
                message=complexity_message(name, value),
                explanation=analysis_explanation(AnalysisRule.COMPLEXITY),
                span=method.span,
                related_ir_ids=(method.id,),
            )
        )
    return tuple(diagnostics)


def _decision_points(node: IrNode, *, in_condition: bool) -> int:
    points = 0
    if node.kind in _DECISION_KINDS:
        points += 1
    if in_condition and node.kind == IrNodeKind.BINARY and node.operator in _SHORT_CIRCUIT:
        points += 1
    for child, role in zip(node.children, node.child_roles, strict=True):
        child_in_condition = in_condition or role == ROLE_CONDITION
        points += _decision_points(child, in_condition=child_in_condition)
    return points
