"""Модель CFG одного метода. Узлы и ребра не являются деревом AST."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.ir.models import SourceSpan


class CfgNodeKind(StrEnum):
    ENTRY = "entry"
    EXIT = "exit"
    STATEMENT = "statement"
    CONDITION = "condition"
    UNSUPPORTED = "unsupported"


class EdgeKind(StrEnum):
    """Вид ребра потока управления.

    throw использует RETURN: отдельного вида ребра для throw в контракте нет,
    оба завершают метод переходом на выход.
    """

    NORMAL = "normal"
    TRUE = "true"
    FALSE = "false"
    LOOP_BACK = "loop_back"
    BREAK = "break"
    CONTINUE = "continue"
    RETURN = "return"


@dataclass(frozen=True, slots=True)
class CfgNode:
    id: str
    kind: CfgNodeKind
    label: str
    ir_node_id: str | None
    span: SourceSpan | None


@dataclass(frozen=True, slots=True)
class CfgEdge:
    id: str
    source_id: str
    target_id: str
    kind: EdgeKind


@dataclass(frozen=True, slots=True)
class CfgLimitation:
    code: str
    message: str
    syntax_type: str | None = None


@dataclass(frozen=True, slots=True)
class CfgGraph:
    """CFG одного метода. entry_id и exit_id пусты, если метода нет."""

    nodes: tuple[CfgNode, ...]
    edges: tuple[CfgEdge, ...]
    entry_id: str | None
    exit_id: str | None
    method_name: str | None
    method_ir_id: str | None
    partial: bool
    limitations: tuple[CfgLimitation, ...]
