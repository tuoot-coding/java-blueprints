"""Построение CFG метода по структурному IR.

Алгоритм (один проход по операторам тела):

1. Создаются синтетические узлы entry и exit.
2. Блок не становится узлом CFG. Его операторы выстраиваются в цепочку.
   Комментарии пропускаются.
3. Обычный оператор (выражение, локальная переменная, присваивание) получает
   входящие ребра и одно нормальное продолжение.
4. if: узел условия, ребро true в ветку then, ребро false в else или на стык.
   Пустая ветка не создает узел: ее входящее ребро становится продолжением.
5. while: узел условия, true ведет в тело, нормальный выход тела возвращается
   к условию ребром loop_back, false выходит из цикла. break собирается на выход
   цикла, continue ведет на условие.
6. classic for: init, затем условие. Если условия нет (for(;;)), ложного ребра
   нет, выход возможен через break или return. continue и нормальный выход тела
   идут в update, если он есть, иначе в условие. update возвращается к условию
   ребром loop_back.
7. return и throw ведут на exit ребром return и не имеют продолжения.
   Отдельного вида ребра throw в контракте нет.
8. break и continue без метки замыкаются на ближайший смоделированный цикл
   (while или classic for). Помеченный переход не угадывается: ребро не строится,
   ставится ограничение labeled_jump.
9. do, enhanced for, try/catch/finally и любой оператор kind=unsupported
   становятся одним непрозрачным узлом с нормальным продолжением. Внутренние
   break, continue и return внутри них не извлекаются. Граф помечается
   partial (method_cfg_partial). Это сознательно грубее, чем неверные ребра.
10. Выходы цепочки, которые не завершили метод, соединяются с exit.

Тернарный оператор и вызовы не порождают ребер: CFG этого этапа операторный.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.graph.models import CfgEdge, CfgGraph, CfgLimitation, CfgNode, CfgNodeKind, EdgeKind
from app.graph.validate import validate_cfg_invariants
from app.ir.models import ROLE_BODY, IrNode, IrNodeKind
from app.texts.graph import (
    FOR_INFINITE_LABEL,
    GRAPH_ENTRY_LABEL,
    GRAPH_EXIT_LABEL,
    graph_limitation_message,
)

_SIMPLE_KINDS = frozenset(
    {
        IrNodeKind.EXPRESSION_STATEMENT,
        IrNodeKind.LOCAL_VARIABLE,
        IrNodeKind.ASSIGNMENT,
        IrNodeKind.METHOD_INVOCATION,
        IrNodeKind.OBJECT_CREATION,
    }
)

_OPAQUE_KINDS = frozenset(
    {
        IrNodeKind.DO,
        IrNodeKind.ENHANCED_FOR,
        IrNodeKind.TRY,
        IrNodeKind.TRY_WITH_RESOURCES,
        IrNodeKind.UNSUPPORTED,
    }
)

_LABEL_LIMIT = 60
_SYNTAX_TOKEN = re.compile(r"^[A-Za-z0-9_]{1,80}$")


@dataclass
class _LoopFrame:
    continue_target: str
    breaks: list[tuple[str, EdgeKind]] = field(default_factory=list)


class _CfgBuilder:
    def __init__(self, method: IrNode) -> None:
        self._method = method
        self._nodes: list[CfgNode] = []
        self._edges: list[CfgEdge] = []
        self._loops: list[_LoopFrame] = []
        self._limitations: list[CfgLimitation] = []
        self._seen_limits: set[tuple[str, str | None]] = set()
        self._partial = False
        self._seq = 0

    def build(self) -> CfgGraph:
        entry_id = self._synthetic(CfgNodeKind.ENTRY, GRAPH_ENTRY_LABEL, None)
        exit_id = self._synthetic(CfgNodeKind.EXIT, GRAPH_EXIT_LABEL, None)
        body = self._method.role_child(ROLE_BODY)
        if body is None:
            self._edge(entry_id, exit_id, EdgeKind.NORMAL)
            self._limit("method_without_body", None)
        else:
            fallthrough = self._statement(body, [(entry_id, EdgeKind.NORMAL)])
            for source_id, kind in fallthrough:
                self._edge(source_id, exit_id, kind)
        return CfgGraph(
            nodes=tuple(self._nodes),
            edges=tuple(self._edges),
            entry_id=entry_id,
            exit_id=exit_id,
            method_name=self._method.name,
            method_ir_id=self._method.id,
            partial=self._partial,
            limitations=tuple(self._limitations),
        )

    def _statement(
        self,
        node: IrNode,
        preds: list[tuple[str, EdgeKind]],
    ) -> list[tuple[str, EdgeKind]]:
        if node.kind == IrNodeKind.COMMENT:
            return preds
        if node.kind == IrNodeKind.BLOCK:
            return self._sequence(_statements(node), preds)
        if node.kind == IrNodeKind.IF:
            return self._if_statement(node, preds)
        if node.kind == IrNodeKind.WHILE:
            return self._while_statement(node, preds)
        if node.kind == IrNodeKind.FOR:
            return self._for_statement(node, preds)
        if node.kind in _OPAQUE_KINDS:
            return self._opaque(node, preds)
        if node.kind in {IrNodeKind.RETURN, IrNodeKind.THROW}:
            return self._exit_transfer(node, preds)
        if node.kind == IrNodeKind.BREAK:
            return self._break_statement(node, preds)
        if node.kind == IrNodeKind.CONTINUE:
            return self._continue_statement(node, preds)
        if node.kind in _SIMPLE_KINDS:
            return self._simple(node, preds)
        return self._opaque(node, preds)

    def _sequence(
        self,
        statements: list[IrNode],
        preds: list[tuple[str, EdgeKind]],
    ) -> list[tuple[str, EdgeKind]]:
        current = preds
        for statement in statements:
            current = self._statement(statement, current)
        return current

    def _simple(
        self, node: IrNode, preds: list[tuple[str, EdgeKind]]
    ) -> list[tuple[str, EdgeKind]]:
        node_id = self._add(node, CfgNodeKind.STATEMENT)
        self._connect(preds, node_id)
        return [(node_id, EdgeKind.NORMAL)]

    def _exit_transfer(
        self,
        node: IrNode,
        preds: list[tuple[str, EdgeKind]],
    ) -> list[tuple[str, EdgeKind]]:
        node_id = self._add(node, CfgNodeKind.STATEMENT)
        self._connect(preds, node_id)
        exit_id = self._exit_id()
        if exit_id is not None:
            self._edge(node_id, exit_id, EdgeKind.RETURN)
        return []

    def _if_statement(
        self,
        node: IrNode,
        preds: list[tuple[str, EdgeKind]],
    ) -> list[tuple[str, EdgeKind]]:
        condition = node.role_child("condition")
        body = node.role_child("body")
        if condition is None or body is None:
            self._limit("incomplete_control", node.syntax_type)
            return self._opaque(node, preds)
        condition_id = self._add(condition, CfgNodeKind.CONDITION)
        self._connect(preds, condition_id)
        then_preds = self._statement(body, [(condition_id, EdgeKind.TRUE)])
        alternative = node.role_child("else")
        if alternative is None:
            else_preds = [(condition_id, EdgeKind.FALSE)]
        else:
            else_preds = self._statement(alternative, [(condition_id, EdgeKind.FALSE)])
        return [*then_preds, *else_preds]

    def _while_statement(
        self,
        node: IrNode,
        preds: list[tuple[str, EdgeKind]],
    ) -> list[tuple[str, EdgeKind]]:
        condition = node.role_child("condition")
        body = node.role_child("body")
        if condition is None or body is None:
            self._limit("incomplete_control", node.syntax_type)
            return self._opaque(node, preds)
        condition_id = self._add(condition, CfgNodeKind.CONDITION)
        self._connect(preds, condition_id)
        frame = _LoopFrame(continue_target=condition_id)
        self._loops.append(frame)
        body_preds = self._statement(body, [(condition_id, EdgeKind.TRUE)])
        self._loops.pop()
        self._loop_back(body_preds, condition_id)
        return [(condition_id, EdgeKind.FALSE), *frame.breaks]

    def _for_statement(
        self,
        node: IrNode,
        preds: list[tuple[str, EdgeKind]],
    ) -> list[tuple[str, EdgeKind]]:
        body = node.role_child("body")
        if body is None:
            self._limit("incomplete_control", node.syntax_type)
            return self._opaque(node, preds)
        init = node.role_child("init")
        condition = node.role_child("condition")
        update = node.role_child("update")
        current = self._statement(init, preds) if init is not None else preds
        if condition is None:
            condition_id = self._synthetic(CfgNodeKind.CONDITION, FOR_INFINITE_LABEL, node)
        else:
            condition_id = self._add(condition, CfgNodeKind.CONDITION)
        self._connect(current, condition_id)
        update_id = self._add(update, CfgNodeKind.STATEMENT) if update is not None else None
        continue_target = update_id if update_id is not None else condition_id
        frame = _LoopFrame(continue_target=continue_target)
        self._loops.append(frame)
        body_preds = self._statement(body, [(condition_id, EdgeKind.TRUE)])
        self._loops.pop()
        self._loop_back(body_preds, continue_target)
        if update_id is not None:
            self._edge(update_id, condition_id, EdgeKind.LOOP_BACK)
        if condition is None:
            return list(frame.breaks)
        return [(condition_id, EdgeKind.FALSE), *frame.breaks]

    def _loop_back(self, preds: list[tuple[str, EdgeKind]], target: str) -> None:
        for source_id, kind in preds:
            edge_kind = EdgeKind.LOOP_BACK if kind == EdgeKind.NORMAL else kind
            self._edge(source_id, target, edge_kind)

    def _break_statement(
        self,
        node: IrNode,
        preds: list[tuple[str, EdgeKind]],
    ) -> list[tuple[str, EdgeKind]]:
        node_id = self._add(node, CfgNodeKind.STATEMENT)
        self._connect(preds, node_id)
        if node.label:
            self._limit("labeled_jump", node.syntax_type)
            return []
        if not self._loops:
            self._limit("break_without_loop", node.syntax_type)
            return []
        self._loops[-1].breaks.append((node_id, EdgeKind.BREAK))
        return []

    def _continue_statement(
        self,
        node: IrNode,
        preds: list[tuple[str, EdgeKind]],
    ) -> list[tuple[str, EdgeKind]]:
        node_id = self._add(node, CfgNodeKind.STATEMENT)
        self._connect(preds, node_id)
        if node.label:
            self._limit("labeled_jump", node.syntax_type)
            return []
        if not self._loops:
            self._limit("continue_without_loop", node.syntax_type)
            return []
        self._edge(node_id, self._loops[-1].continue_target, EdgeKind.CONTINUE)
        return []

    def _opaque(
        self, node: IrNode, preds: list[tuple[str, EdgeKind]]
    ) -> list[tuple[str, EdgeKind]]:
        syntax_type = _safe_syntax(node.reason or node.syntax_type)
        self._limit("method_cfg_partial", syntax_type)
        self._limit("opaque_statement", syntax_type)
        node_id = self._add(node, CfgNodeKind.UNSUPPORTED)
        self._connect(preds, node_id)
        return [(node_id, EdgeKind.NORMAL)]

    def _add(self, node: IrNode, kind: CfgNodeKind) -> str:
        self._seq += 1
        node_id = f"c{self._seq}_{kind.value}"
        self._nodes.append(
            CfgNode(
                id=node_id,
                kind=kind,
                label=_compact_label(node.source_text),
                ir_node_id=node.id,
                span=node.span,
            )
        )
        return node_id

    def _synthetic(self, kind: CfgNodeKind, label: str, owner: IrNode | None) -> str:
        self._seq += 1
        node_id = f"c{self._seq}_{kind.value}"
        self._nodes.append(
            CfgNode(
                id=node_id,
                kind=kind,
                label=label,
                ir_node_id=owner.id if owner is not None else None,
                span=owner.span if owner is not None else None,
            )
        )
        return node_id

    def _connect(self, preds: list[tuple[str, EdgeKind]], target: str) -> None:
        for source_id, kind in preds:
            self._edge(source_id, target, kind)

    def _edge(self, source_id: str, target_id: str, kind: EdgeKind) -> None:
        self._seq += 1
        self._edges.append(
            CfgEdge(
                id=f"e{self._seq}_{kind.value}",
                source_id=source_id,
                target_id=target_id,
                kind=kind,
            )
        )

    def _exit_id(self) -> str | None:
        for node in self._nodes:
            if node.kind == CfgNodeKind.EXIT:
                return node.id
        return None

    def _limit(self, code: str, syntax_type: str | None) -> None:
        safe_syntax = _safe_syntax(syntax_type)
        key = (code, safe_syntax)
        if key in self._seen_limits:
            return
        self._seen_limits.add(key)
        if code != "method_without_body":
            self._partial = True
        self._limitations.append(
            CfgLimitation(
                code=code,
                message=graph_limitation_message(code, safe_syntax),
                syntax_type=safe_syntax,
            )
        )


def build_method_cfg(ir_method: IrNode) -> CfgGraph:
    """Строит CFG метода или конструктора и проверяет инварианты формы."""
    graph = _CfgBuilder(ir_method).build()
    problems = validate_cfg_invariants(graph)
    if problems:
        joined = ", ".join(problems)
        raise RuntimeError(f"Инварианты CFG нарушены: {joined}")
    return graph


def _statements(block: IrNode) -> list[IrNode]:
    return [child for child in block.children if child.kind != IrNodeKind.COMMENT]


def _compact_label(source_text: str) -> str:
    compact = " ".join(source_text.split())
    if len(compact) <= _LABEL_LIMIT:
        return compact
    return compact[: _LABEL_LIMIT - 3] + "..."


def _safe_syntax(value: str | None) -> str | None:
    if value is None or _SYNTAX_TOKEN.fullmatch(value) is None:
        return None
    return value
