"""Обход структурного IR и выборка методов."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.ir.models import IrNode, IrNodeKind


def walk_ir(node: IrNode) -> Iterator[IrNode]:
    """Прямой обход: узел, затем дочерние слева направо."""
    yield node
    for child in node.children:
        yield from walk_ir(child)


def list_methods(root: IrNode) -> tuple[IrNode, ...]:
    """Методы и конструкторы (включая compact record) в порядке исходника."""
    return tuple(
        node
        for node in walk_ir(root)
        if node.kind
        in {IrNodeKind.METHOD, IrNodeKind.CONSTRUCTOR, IrNodeKind.COMPACT_CONSTRUCTOR}
    )


def find_method_by_name(root: IrNode, name: str) -> IrNode | None:
    """Первый метод или конструктор с точным именем. None, если имени нет."""
    for method in list_methods(root):
        if method.name == name:
            return method
    return None


def count_unsupported(root: IrNode) -> int:
    """Число узлов kind=unsupported. Вложенные в непрозрачный лист не дублируются."""
    return sum(1 for node in walk_ir(root) if node.kind == IrNodeKind.UNSUPPORTED)


@dataclass(frozen=True, slots=True)
class IrSummary:
    """Сводка IR для ответа API. kind_counts не содержит исходный текст."""

    node_count: int
    class_names: tuple[str, ...]
    method_names: tuple[str, ...]
    kind_counts: Mapping[str, int]
    unsupported_count: int


def summarize_ir(root: IrNode) -> IrSummary:
    """Считает узлы, имена классов и методов. Имена берутся из полей IR, не из эвристик."""
    counts: dict[str, int] = {}
    class_names: list[str] = []
    method_names: list[str] = []
    unsupported_count = 0
    node_count = 0
    for node in walk_ir(root):
        node_count += 1
        counts[node.kind.value] = counts.get(node.kind.value, 0) + 1
        if node.kind in {
            IrNodeKind.CLASS,
            IrNodeKind.INTERFACE,
            IrNodeKind.ENUM,
            IrNodeKind.RECORD,
        } and node.name:
            class_names.append(node.name)
        if (
            node.kind
            in {IrNodeKind.METHOD, IrNodeKind.CONSTRUCTOR, IrNodeKind.COMPACT_CONSTRUCTOR}
            and node.name
        ):
            method_names.append(node.name)
        if node.kind == IrNodeKind.UNSUPPORTED:
            unsupported_count += 1
    return IrSummary(
        node_count=node_count,
        class_names=tuple(class_names),
        method_names=tuple(method_names),
        kind_counts=MappingProxyType(dict(sorted(counts.items()))),
        unsupported_count=unsupported_count,
    )
