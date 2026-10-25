"""Излишества кода: длинные/перегруженные методы и дублирование логики."""

from __future__ import annotations

import hashlib
import re

from app.analysis.models import AnalysisDiagnostic, AnalysisSeverity
from app.ir.models import ROLE_BODY, IrNode, IrNodeKind
from app.ir.query import list_methods
from app.texts.analysis import (
    AnalysisRule,
    analysis_explanation,
    duplicate_logic_message,
    long_method_message,
)

# Пороги длины метода (строки исходника внутри тела).
LONG_METHOD_LINES = 40
VERY_LONG_METHOD_LINES = 80
# Порог числа значимых операторов в теле.
LONG_METHOD_STATEMENTS = 28
VERY_LONG_METHOD_STATEMENTS = 55
# Минимальная длина нормализованного тела для сравнения дублей.
MIN_DUP_BODY_CHARS = 40
# Похожесть сигнатур statement-kind (Жаккард) для near-duplicate.
NEAR_DUP_JACCARD = 0.82
MIN_KIND_SEQ_LEN = 6

_WS_RE = re.compile(r"\s+")
_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def find_bloat(root: IrNode) -> tuple[AnalysisDiagnostic, ...]:
    """Длинные методы и дублирующаяся логика по структурному IR."""
    diagnostics: list[AnalysisDiagnostic] = []
    methods = list_methods(root)
    for method in methods:
        diagnostics.extend(_long_method_issues(method))
    diagnostics.extend(_duplicate_method_logic(methods))
    return tuple(diagnostics)


def _long_method_issues(method: IrNode) -> list[AnalysisDiagnostic]:
    body = method.role_child(ROLE_BODY)
    if body is None:
        return []
    line_span = max(1, method.span.end_line - method.span.start_line + 1)
    statements = _count_statements(body)
    name = method.name or "без имени"
    if line_span < LONG_METHOD_LINES and statements < LONG_METHOD_STATEMENTS:
        return []
    severity = AnalysisSeverity.WARNING
    if line_span >= VERY_LONG_METHOD_LINES or statements >= VERY_LONG_METHOD_STATEMENTS:
        severity = AnalysisSeverity.WARNING
    return [
        AnalysisDiagnostic(
            severity=severity,
            rule_id=AnalysisRule.LONG_METHOD,
            message=long_method_message(name, line_span, statements),
            explanation=analysis_explanation(AnalysisRule.LONG_METHOD),
            span=method.span,
            related_ir_ids=(method.id,),
        )
    ]


def _duplicate_method_logic(methods: tuple[IrNode, ...]) -> list[AnalysisDiagnostic]:
    prepared: list[tuple[IrNode, str, tuple[str, ...]]] = []
    for method in methods:
        body = method.role_child(ROLE_BODY)
        if body is None:
            continue
        normalized = _normalize_body(body.source_text)
        if len(normalized) < MIN_DUP_BODY_CHARS:
            continue
        kinds = _statement_kind_signature(body)
        prepared.append((method, normalized, kinds))

    diagnostics: list[AnalysisDiagnostic] = []
    seen_pairs: set[tuple[str, str]] = set()
    for index, (left, left_norm, left_kinds) in enumerate(prepared):
        left_hash = hashlib.sha1(left_norm.encode("utf-8")).hexdigest()
        for right, right_norm, right_kinds in prepared[index + 1 :]:
            pair_key = tuple(sorted((left.id, right.id)))
            if pair_key in seen_pairs:
                continue
            right_hash = hashlib.sha1(right_norm.encode("utf-8")).hexdigest()
            exact = left_hash == right_hash
            similar = (
                not exact
                and len(left_kinds) >= MIN_KIND_SEQ_LEN
                and len(right_kinds) >= MIN_KIND_SEQ_LEN
                and _jaccard(left_kinds, right_kinds) >= NEAR_DUP_JACCARD
            )
            if not exact and not similar:
                continue
            seen_pairs.add(pair_key)
            left_name = left.name or "?"
            right_name = right.name or "?"
            diagnostics.append(
                AnalysisDiagnostic(
                    severity=AnalysisSeverity.WARNING,
                    rule_id=AnalysisRule.DUPLICATE_LOGIC,
                    message=duplicate_logic_message(left_name, right_name, exact=exact),
                    explanation=analysis_explanation(AnalysisRule.DUPLICATE_LOGIC),
                    span=left.span,
                    related_ir_ids=(left.id, right.id),
                )
            )
    return diagnostics


def _count_statements(node: IrNode) -> int:
    interesting = {
        IrNodeKind.LOCAL_VARIABLE,
        IrNodeKind.EXPRESSION_STATEMENT,
        IrNodeKind.ASSIGNMENT,
        IrNodeKind.RETURN,
        IrNodeKind.BREAK,
        IrNodeKind.CONTINUE,
        IrNodeKind.THROW,
        IrNodeKind.IF,
        IrNodeKind.WHILE,
        IrNodeKind.DO,
        IrNodeKind.FOR,
        IrNodeKind.ENHANCED_FOR,
        IrNodeKind.TRY,
        IrNodeKind.METHOD_INVOCATION,
    }
    total = 1 if node.kind in interesting else 0
    for child in node.children:
        total += _count_statements(child)
    return total


def _statement_kind_signature(node: IrNode) -> tuple[str, ...]:
    kinds: list[str] = []

    def walk(current: IrNode) -> None:
        if current.kind not in {
            IrNodeKind.BLOCK,
            IrNodeKind.COMMENT,
            IrNodeKind.IDENTIFIER,
            IrNodeKind.LITERAL,
        }:
            kinds.append(current.kind.value)
        for child in current.children:
            walk(child)

    walk(node)
    return tuple(kinds)


def _normalize_body(text: str) -> str:
    # Убираем пробелы и нормализуем идентификаторы в плейсхолдеры - сравниваем структуру.
    collapsed = _WS_RE.sub(" ", text.strip())
    return _IDENT_RE.sub("ID", collapsed)


def _jaccard(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)
