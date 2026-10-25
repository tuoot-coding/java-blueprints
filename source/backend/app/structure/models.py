"""Структурные блоки для визуального дерева. Это не ребра CFG."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.ir.models import SourceSpan


class LinkKind(StrEnum):
    """Иерархическая или последовательная связь блока. Не вид ребра CFG."""

    NEXT = "next"
    BODY = "body"
    ELSE = "else"
    CONDITION = "condition"
    VALUE = "value"
    ARGUMENTS = "arguments"
    PARAMETERS = "parameters"
    CHILDREN = "children"


@dataclass(frozen=True, slots=True)
class StructuralLink:
    kind: LinkKind
    target_id: str


@dataclass(frozen=True, slots=True)
class StructuralBlock:
    """Один блок Scratch-подобного дерева, привязанный к узлу IR."""

    id: str
    type: str
    parent_id: str | None
    label: str
    ir_node_id: str
    span: SourceSpan
    editable: bool
    supported_operations: tuple[str, ...]
    links: tuple[StructuralLink, ...]
