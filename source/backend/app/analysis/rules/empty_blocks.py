"""Пустые тела и минимальные структурные подозрения.

Семантическое правило «одинаковые условия if» отложено. Здесь сравнивается только
точный source_text условий у соседних if одного блока.
"""

from __future__ import annotations

from app.analysis.models import AnalysisDiagnostic, AnalysisSeverity
from app.ir.models import IrNode, IrNodeKind
from app.ir.query import walk_ir
from app.texts.analysis import (
    AnalysisRule,
    analysis_explanation,
    duplicate_if_message,
    empty_control_message,
    empty_if_else_message,
    empty_method_message,
    infinite_for_message,
)

_CONTROL_WITH_BODY = frozenset(
    {
        IrNodeKind.IF,
        IrNodeKind.WHILE,
        IrNodeKind.DO,
        IrNodeKind.FOR,
        IrNodeKind.ENHANCED_FOR,
    }
)


def find_empty_blocks(root: IrNode) -> tuple[AnalysisDiagnostic, ...]:
    diagnostics: list[AnalysisDiagnostic] = []
    for node in walk_ir(root):
        if node.kind in {IrNodeKind.METHOD, IrNodeKind.CONSTRUCTOR}:
            body = node.role_child("body")
            if body is not None and _is_empty_block(body):
                diagnostics.append(
                    _diagnostic(
                        AnalysisSeverity.WARNING,
                        AnalysisRule.EMPTY_METHOD,
                        empty_method_message(node.name or "без имени"),
                        body,
                    )
                )
        if node.kind == IrNodeKind.IF:
            diagnostics.extend(_inspect_if(node))
        elif node.kind in _CONTROL_WITH_BODY:
            body = node.role_child("body")
            if body is not None and _is_empty_block(body):
                diagnostics.append(
                    _diagnostic(
                        AnalysisSeverity.HINT,
                        AnalysisRule.EMPTY_CONTROL,
                        empty_control_message(),
                        body,
                    )
                )
        if node.kind == IrNodeKind.FOR:
            diagnostics.extend(_inspect_infinite_for(node))
        if node.kind == IrNodeKind.BLOCK:
            diagnostics.extend(_duplicate_if_conditions(node))
    return tuple(diagnostics)


def _inspect_if(node: IrNode) -> list[AnalysisDiagnostic]:
    body = node.role_child("body")
    alternative = node.role_child("else")
    if body is None or not _is_empty_block(body):
        return []
    if alternative is not None:
        return [
            _diagnostic(
                AnalysisSeverity.WARNING,
                AnalysisRule.EMPTY_IF_ELSE,
                empty_if_else_message(),
                node,
            )
        ]
    return [
        _diagnostic(
            AnalysisSeverity.HINT,
            AnalysisRule.EMPTY_CONTROL,
            empty_control_message(),
            body,
        )
    ]


def _inspect_infinite_for(node: IrNode) -> list[AnalysisDiagnostic]:
    if node.role_child("condition") is not None:
        return []
    body = node.role_child("body")
    if body is None:
        return []
    if any(item.kind == IrNodeKind.UNSUPPORTED for item in walk_ir(body)):
        return []
    if any(item.kind == IrNodeKind.BREAK for item in walk_ir(body)):
        return []
    return [
        _diagnostic(
            AnalysisSeverity.HINT,
            AnalysisRule.INFINITE_FOR,
            infinite_for_message(),
            node,
        )
    ]


def _duplicate_if_conditions(block: IrNode) -> list[AnalysisDiagnostic]:
    diagnostics: list[AnalysisDiagnostic] = []
    previous_text: str | None = None
    for child in block.children:
        if child.kind != IrNodeKind.IF:
            previous_text = None
            continue
        condition = child.role_child("condition")
        text = condition.source_text if condition is not None else None
        if text is not None and text == previous_text:
            diagnostics.append(
                _diagnostic(
                    AnalysisSeverity.HINT,
                    AnalysisRule.DUPLICATE_IF,
                    duplicate_if_message(),
                    child,
                )
            )
        previous_text = text
    return diagnostics


def _is_empty_block(node: IrNode) -> bool:
    return node.kind == IrNodeKind.BLOCK and all(
        child.kind == IrNodeKind.COMMENT for child in node.children
    )


def _diagnostic(
    severity: AnalysisSeverity,
    rule: AnalysisRule,
    message: str,
    node: IrNode,
) -> AnalysisDiagnostic:
    return AnalysisDiagnostic(
        severity=severity,
        rule_id=rule,
        message=message,
        explanation=analysis_explanation(rule),
        span=node.span,
        related_ir_ids=(node.id,),
    )
