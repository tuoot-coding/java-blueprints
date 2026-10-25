"""Преобразование IR в плоский список структурных блоков.

Связи children/body/parameters описывают вложенность синтаксиса.
Связь next соединяет соседние операторы одного блока и не является ребром CFG.
Перетаскивание такого блока не меняет Java: editable остается False.
"""

from __future__ import annotations

import itertools

from app.ir.models import (
    ROLE_ARGUMENTS,
    ROLE_BODY,
    ROLE_CHILDREN,
    ROLE_CONDITION,
    ROLE_ELSE,
    ROLE_INIT,
    ROLE_LEFT,
    ROLE_OBJECT,
    ROLE_PARAMETERS,
    ROLE_RIGHT,
    ROLE_UPDATE,
    ROLE_VALUE,
    IrNode,
    IrNodeKind,
)
from app.structure.models import LinkKind, StructuralBlock, StructuralLink
from app.texts.structure import structure_block_label

_ROLE_TO_LINK = {
    ROLE_BODY: LinkKind.BODY,
    ROLE_ELSE: LinkKind.ELSE,
    ROLE_CONDITION: LinkKind.CONDITION,
    ROLE_PARAMETERS: LinkKind.PARAMETERS,
    ROLE_ARGUMENTS: LinkKind.ARGUMENTS,
    ROLE_VALUE: LinkKind.VALUE,
    ROLE_LEFT: LinkKind.VALUE,
    ROLE_RIGHT: LinkKind.VALUE,
    ROLE_OBJECT: LinkKind.CHILDREN,
    ROLE_INIT: LinkKind.CHILDREN,
    ROLE_UPDATE: LinkKind.CHILDREN,
    ROLE_CHILDREN: LinkKind.CHILDREN,
}


def build_structural_blocks(root: IrNode) -> tuple[StructuralBlock, ...]:
    """Прямой порядок: родитель в списке раньше своих дочерних блоков."""
    blocks: list[StructuralBlock] = []

    def visit(node: IrNode, parent_id: str | None, next_id: str | None) -> None:
        links = [
            StructuralLink(kind=_ROLE_TO_LINK.get(role, LinkKind.CHILDREN), target_id=child.id)
            for child, role in zip(node.children, node.child_roles, strict=True)
        ]
        if next_id is not None:
            links.append(StructuralLink(kind=LinkKind.NEXT, target_id=next_id))
        blocks.append(
            StructuralBlock(
                id=node.id,
                type=node.kind.value,
                parent_id=parent_id,
                label=structure_block_label(node.kind.value, node.name),
                ir_node_id=node.id,
                span=node.span,
                editable=node.editable,
                supported_operations=(),
                links=tuple(links),
            )
        )
        sibling_next = _statement_next_ids(node)
        for child in node.children:
            visit(child, node.id, sibling_next.get(child.id))

    visit(root, None, None)
    return tuple(blocks)


def _statement_next_ids(node: IrNode) -> dict[str, str]:
    """next только между операторами блока. Комментарии последовательность не ведут."""
    if node.kind != IrNodeKind.BLOCK:
        return {}
    statements = [child for child in node.children if child.kind != IrNodeKind.COMMENT]
    return {current.id: nxt.id for current, nxt in itertools.pairwise(statements)}
