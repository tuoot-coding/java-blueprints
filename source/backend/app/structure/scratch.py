"""Модульная блок-схема логической структуры (ISO 5807 / ГОСТ 19.701).

Схема описывает иерархию модулей программы: compilation unit -> class -> method ->
операторы. Это не CFG: связи body/else/next отражают вложенность и порядок
операторов одного блока. Синтетические узлы start/end обозначают вход и выход метода.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from app.ir.models import (
    ROLE_BODY,
    ROLE_CONDITION,
    ROLE_ELSE,
    ROLE_PARAMETERS,
    IrNode,
    IrNodeKind,
    SourceSpan,
)
from app.ir.query import list_methods


@dataclass(frozen=True, slots=True)
class ScratchLink:
    kind: str
    target_id: str


@dataclass(frozen=True, slots=True)
class ScratchBlock:
    id: str
    kind: str
    label: str
    ir_node_id: str
    span: SourceSpan
    parent_id: str | None
    nest_level: int
    color: str
    links: tuple[ScratchLink, ...]
    # Текстовый фрагмент исходника для обратной генерации; пусто у синтетических узлов.
    source_snippet: str = ""
    # Идентификатор логического модуля (class/method), к которому относится блок.
    module_id: str | None = None
    editable: bool = True


@dataclass(frozen=True, slots=True)
class ScratchModule:
    """Логический модуль: класс или метод как единица декомпозиции."""

    id: str
    kind: str
    name: str
    parent_module_id: str | None
    root_block_id: str
    block_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScratchProgram:
    """Модульная логическая структура программы (не поток управления CFG)."""

    method_name: str | None
    method_ir_id: str | None
    blocks: tuple[ScratchBlock, ...]
    root_block_ids: tuple[str, ...]
    modules: tuple[ScratchModule, ...] = ()
    method_names: tuple[str, ...] = ()


# Цвета по ролям модульной блок-схемы.
_KIND_COLORS = {
    "class": "#2563eb",
    "method": "#7c3aed",
    "module": "#4f46e5",
    "start": "#16a34a",
    "end": "#15803d",
    "parameter": "#64748b",
    "variable": "#0d9488",
    "assignment": "#0891b2",
    "call": "#0284c7",
    "if": "#ca8a04",
    "else": "#a16207",
    "while": "#c026d3",
    "do": "#c026d3",
    "for": "#db2777",
    "foreach": "#db2777",
    "return": "#dc2626",
    "break": "#ea580c",
    "continue": "#ea580c",
    "throw": "#b91c1c",
    "try": "#4f46e5",
    "catch": "#4338ca",
    "finally": "#3730a3",
    "switch": "#d97706",
    "case": "#b45309",
    "synchronized": "#0f766e",
    "labeled": "#57534e",
    "assert": "#a16207",
    "yield": "#be123c",
    "interface": "#1d4ed8",
    "enum": "#1e40af",
    "record": "#1e3a8a",
    "expression": "#475569",
    "unsupported": "#71717a",
    "block": "#334155",
}

_STATEMENT_KINDS = {
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
    IrNodeKind.TRY_WITH_RESOURCES,
    IrNodeKind.BLOCK,
    IrNodeKind.UNSUPPORTED,
    IrNodeKind.METHOD_INVOCATION,
    IrNodeKind.SWITCH,
    IrNodeKind.SYNCHRONIZED,
    IrNodeKind.LABELED,
    IrNodeKind.ASSERT,
    IrNodeKind.YIELD,
}

_TYPE_KINDS = {
    IrNodeKind.CLASS,
    IrNodeKind.INTERFACE,
    IrNodeKind.ENUM,
    IrNodeKind.RECORD,
}


def build_scratch_program(root: IrNode) -> ScratchProgram:
    """Строит модульную блок-схему по всем классам и методам compilation unit."""
    blocks: list[ScratchBlock] = []
    modules: list[ScratchModule] = []
    roots: list[str] = []
    method_names: list[str] = []

    types = [child for child in root.children if child.kind in _TYPE_KINDS]
    if types:
        for type_node in types:
            roots.append(type_node.id)
            _emit_class(type_node, None, 0, blocks, modules, method_names)
    else:
        for method in list_methods(root):
            roots.append(method.id)
            _emit_method(method, None, 0, blocks, modules, method_names, parent_module_id=None)
        if not roots:
            for child in root.children:
                if child.kind in {IrNodeKind.PACKAGE, IrNodeKind.IMPORT, IrNodeKind.COMMENT}:
                    continue
                roots.append(child.id)
                _emit_generic(child, None, 0, blocks, role_hint=None, module_id=None)

    primary = list_methods(root)
    primary_method = primary[0] if primary else None
    flattened = _flatten_anonymous_blocks(blocks)
    return ScratchProgram(
        method_name=primary_method.name if primary_method else None,
        method_ir_id=primary_method.id if primary_method else None,
        blocks=tuple(flattened),
        root_block_ids=tuple(roots),
        modules=tuple(modules),
        method_names=tuple(method_names),
    )


def _flatten_anonymous_blocks(blocks: list[ScratchBlock]) -> list[ScratchBlock]:
    """Убирает избыточные узлы kind=block: дети поднимаются к родителю, связи перешиваются."""
    by_id = {block.id: block for block in blocks}
    wrappers = [block for block in blocks if block.kind == "block"]
    if not wrappers:
        return blocks

    remove_ids: set[str] = {wrapper.id for wrapper in wrappers}
    retarget: dict[str, str] = {}
    parent_of: dict[str, str | None] = {block.id: block.parent_id for block in blocks}
    extra_next: dict[str, str] = {}

    for wrapper in wrappers:
        body = next((link.target_id for link in wrapper.links if link.kind == "body"), None)
        nxt = next((link.target_id for link in wrapper.links if link.kind == "next"), None)
        chain: list[str] = []
        current = body
        seen: set[str] = set()
        while current and current in by_id and current not in seen and current not in remove_ids:
            seen.add(current)
            chain.append(current)
            current = next(
                (
                    link.target_id
                    for link in by_id[current].links
                    if link.kind == "next" and link.target_id in by_id
                ),
                None,
            )
        if not chain:
            chain = [
                block.id
                for block in blocks
                if block.parent_id == wrapper.id and block.id not in remove_ids
            ]
        if chain:
            retarget[wrapper.id] = chain[0]
            for child_id in chain:
                parent_of[child_id] = wrapper.parent_id
            if nxt and nxt not in remove_ids:
                extra_next[chain[-1]] = nxt

    result: list[ScratchBlock] = []
    for block in blocks:
        if block.id in remove_ids:
            continue
        links: list[ScratchLink] = []
        for link in block.links:
            target = link.target_id
            while target in retarget:
                target = retarget[target]
            if target in remove_ids or target == block.id:
                continue
            links.append(ScratchLink(kind=link.kind, target_id=target))
        if block.id in extra_next and not any(link.kind == "next" for link in links):
            links.append(ScratchLink(kind="next", target_id=extra_next[block.id]))
        new_parent = parent_of.get(block.id, block.parent_id)
        nest = block.nest_level
        if new_parent != block.parent_id:
            nest = max(0, nest - 1)
        result.append(
            ScratchBlock(
                id=block.id,
                kind=block.kind,
                label=block.label,
                ir_node_id=block.ir_node_id,
                span=block.span,
                parent_id=new_parent,
                nest_level=nest,
                color=block.color,
                links=tuple(links),
                source_snippet=block.source_snippet,
                module_id=block.module_id,
                editable=block.editable,
            )
        )
    return result


def serialize_scratch_outline(program: ScratchProgram) -> str:
    """Текстовый контур модульной схемы для LLM и сравнения."""
    by_id = {block.id: block for block in program.blocks}
    lines: list[str] = [
        f"modules={len(program.modules)} methods={','.join(program.method_names) or '-'}",
        f"blocks={len(program.blocks)}",
        "ORDER_RULES: next=sequence body=then/loop-body else=alternate children=nested",
    ]
    for module in program.modules:
        indent = "  " if module.parent_module_id else ""
        lines.append(f"{indent}[{module.kind}] {module.name} id={module.id}")
        for block_id in module.block_ids:
            block = by_id.get(block_id)
            if block is None or block.kind in {"class", "method"}:
                continue
            nest = "  " * (block.nest_level + 1)
            snippet = block.source_snippet.replace("\n", " ").strip()
            if len(snippet) > 48:
                snippet = snippet[:48] + "..."
            extra = f" :: {snippet}" if snippet else ""
            outs = ",".join(
                f"{link.kind}->{link.target_id}"
                for link in block.links
                if link.kind in {"next", "body", "else", "children"}
            )
            link_bit = f" links[{outs}]" if outs else ""
            lines.append(f"{nest}{block.kind}:{block.id} {block.label}{extra}{link_bit}")
    return "\n".join(lines)


def _emit_class(
    node: IrNode,
    parent_id: str | None,
    nest: int,
    out: list[ScratchBlock],
    modules: list[ScratchModule],
    method_names: list[str],
) -> None:
    type_kind = {
        IrNodeKind.CLASS: "class",
        IrNodeKind.INTERFACE: "interface",
        IrNodeKind.ENUM: "enum",
        IrNodeKind.RECORD: "record",
    }.get(node.kind, "class")
    members = [
        child
        for child in node.children
        if child.kind
        in {
            IrNodeKind.METHOD,
            IrNodeKind.CONSTRUCTOR,
            IrNodeKind.FIELD,
            IrNodeKind.UNSUPPORTED,
        }
    ]
    links = [ScratchLink(kind="children", target_id=item.id) for item in members]
    _append_next_chain(links, members)
    class_name = node.name or "?"
    type_label = {
        "class": "класс",
        "interface": "интерфейс",
        "enum": "enum",
        "record": "record",
    }.get(type_kind, "класс")
    out.append(
        ScratchBlock(
            id=node.id,
            kind=type_kind,
            label=f"модуль {type_label} {class_name}",
            ir_node_id=node.id,
            span=node.span,
            parent_id=parent_id,
            nest_level=nest,
            color=_KIND_COLORS.get(type_kind, _KIND_COLORS["class"]),
            links=tuple(links),
            source_snippet=_snippet(node),
            module_id=node.id,
            editable=False,
        )
    )
    member_ids: list[str] = [node.id]
    for item in members:
        if item.kind in {IrNodeKind.METHOD, IrNodeKind.CONSTRUCTOR}:
            child_ids = _emit_method(
                item,
                node.id,
                nest + 1,
                out,
                modules,
                method_names,
                parent_module_id=node.id,
            )
            member_ids.extend(child_ids)
        else:
            _emit_generic(item, node.id, nest + 1, out, role_hint=None, module_id=node.id)
            member_ids.append(item.id)
    modules.append(
        ScratchModule(
            id=node.id,
            kind=type_kind,
            name=class_name,
            parent_module_id=None,
            root_block_id=node.id,
            block_ids=tuple(member_ids),
        )
    )


def _emit_method(
    node: IrNode,
    parent_id: str | None,
    nest: int,
    out: list[ScratchBlock],
    modules: list[ScratchModule],
    method_names: list[str],
    *,
    parent_module_id: str | None,
) -> list[str]:
    """Возвращает id блоков, принадлежащих методу (включая start/end)."""
    params = list(node.role_children(ROLE_PARAMETERS))
    body = node.role_child(ROLE_BODY)
    body_statements: list[IrNode] = []
    if body is not None:
        body_statements = _statement_children(body)

    start_id = f"{node.id}__start"
    end_id = f"{node.id}__end"
    name = node.name or "method"
    method_names.append(name)

    links: list[ScratchLink] = [ScratchLink(kind="parameters", target_id=p.id) for p in params]
    links.append(ScratchLink(kind="body", target_id=start_id))

    out.append(
        ScratchBlock(
            id=node.id,
            kind="method",
            label=f"модуль метод {name}",
            ir_node_id=node.id,
            span=node.span,
            parent_id=parent_id,
            nest_level=nest,
            color=_KIND_COLORS["method"],
            links=tuple(links),
            source_snippet=_snippet(node),
            module_id=node.id,
            editable=False,
        )
    )

    collected: list[str] = [node.id, start_id]
    for param in params:
        out.append(
            ScratchBlock(
                id=param.id,
                kind="parameter",
                label=f"параметр {param.name or param.type_text or '?'}",
                ir_node_id=param.id,
                span=param.span,
                parent_id=node.id,
                nest_level=nest + 1,
                color=_KIND_COLORS["parameter"],
                links=(),
                source_snippet=_snippet(param),
                module_id=node.id,
                editable=True,
            )
        )
        collected.append(param.id)

    first_body_id = body_statements[0].id if body_statements else end_id
    out.append(
        ScratchBlock(
            id=start_id,
            kind="start",
            label="начало",
            ir_node_id=node.id,
            span=node.span,
            parent_id=node.id,
            nest_level=nest + 1,
            color=_KIND_COLORS["start"],
            links=(ScratchLink(kind="next", target_id=first_body_id),),
            source_snippet="",
            module_id=node.id,
            editable=False,
        )
    )

    before_count = len(out)
    for stmt in body_statements:
        _emit_statement(stmt, node.id, nest + 1, out, module_id=node.id)
    for block in out[before_count:]:
        collected.append(block.id)

    _patch_method_next_links(out, body_statements, end_id)

    out.append(
        ScratchBlock(
            id=end_id,
            kind="end",
            label="конец",
            ir_node_id=node.id,
            span=node.span,
            parent_id=node.id,
            nest_level=nest + 1,
            color=_KIND_COLORS["end"],
            links=(),
            source_snippet="",
            module_id=node.id,
            editable=False,
        )
    )
    collected.append(end_id)

    modules.append(
        ScratchModule(
            id=node.id,
            kind="method",
            name=name,
            parent_module_id=parent_module_id,
            root_block_id=node.id,
            block_ids=tuple(dict.fromkeys(collected)),
        )
    )
    return collected


def _patch_method_next_links(
    out: list[ScratchBlock],
    body_statements: list[IrNode],
    end_id: str,
) -> None:
    """Дописывает next между операторами тела метода и к узлу end."""
    if not body_statements:
        return
    next_map: dict[str, str] = {
        current.id: nxt.id for current, nxt in itertools.pairwise(body_statements)
    }
    last = body_statements[-1]
    if last.kind not in {IrNodeKind.RETURN, IrNodeKind.THROW}:
        next_map[last.id] = end_id
    for index, block in enumerate(out):
        target = next_map.get(block.id)
        if target is None:
            continue
        if any(link.kind == "next" and link.target_id == target for link in block.links):
            continue
        new_links = [*list(block.links), ScratchLink(kind="next", target_id=target)]
        out[index] = ScratchBlock(
            id=block.id,
            kind=block.kind,
            label=block.label,
            ir_node_id=block.ir_node_id,
            span=block.span,
            parent_id=block.parent_id,
            nest_level=block.nest_level,
            color=block.color,
            links=tuple(new_links),
            source_snippet=block.source_snippet,
            module_id=block.module_id,
            editable=block.editable,
        )


def _emit_statement(
    node: IrNode,
    parent_id: str | None,
    nest: int,
    out: list[ScratchBlock],
    *,
    module_id: str | None,
) -> None:
    if node.kind == IrNodeKind.IF:
        _emit_if(node, parent_id, nest, out, module_id=module_id)
        return
    if node.kind in {IrNodeKind.WHILE, IrNodeKind.DO, IrNodeKind.FOR, IrNodeKind.ENHANCED_FOR}:
        _emit_loop(node, parent_id, nest, out, module_id=module_id)
        return
    if node.kind in {IrNodeKind.TRY, IrNodeKind.TRY_WITH_RESOURCES}:
        _emit_try(node, parent_id, nest, out, module_id=module_id)
        return
    if node.kind == IrNodeKind.SWITCH:
        _emit_switch(node, parent_id, nest, out, module_id=module_id)
        return
    if node.kind == IrNodeKind.SYNCHRONIZED:
        _emit_synchronized(node, parent_id, nest, out, module_id=module_id)
        return
    if node.kind == IrNodeKind.LABELED:
        _emit_labeled(node, parent_id, nest, out, module_id=module_id)
        return
    if node.kind == IrNodeKind.BLOCK:
        # Без промежуточного узла "block": операторы сразу под parent.
        children = _statement_children(node)
        for child in children:
            _emit_statement(child, parent_id, nest, out, module_id=module_id)
        for index in range(len(children) - 1):
            _ensure_next_link(out, children[index].id, children[index + 1].id)
        return
    _emit_generic(node, parent_id, nest, out, role_hint=None, module_id=module_id)


def _emit_if(
    node: IrNode,
    parent_id: str | None,
    nest: int,
    out: list[ScratchBlock],
    *,
    module_id: str | None,
) -> None:
    condition = node.role_child(ROLE_CONDITION)
    then_body = node.role_child(ROLE_BODY) or node.role_child("consequence")
    else_body = node.role_child(ROLE_ELSE)
    if then_body is None:
        for child, role in zip(node.children, node.child_roles, strict=True):
            if role not in {ROLE_CONDITION, ROLE_ELSE}:
                then_body = child
                break

    then_stmts = _as_statements(then_body)
    else_stmts = _as_statements(else_body) if else_body is not None else []

    links: list[ScratchLink] = []
    if condition is not None:
        links.append(ScratchLink(kind="condition", target_id=condition.id))
    if then_stmts:
        links.append(ScratchLink(kind="body", target_id=then_stmts[0].id))
        _append_next_chain(links, then_stmts)
    else_block_id: str | None = None
    if else_body is not None:
        else_block_id = f"{node.id}__else"
        links.append(ScratchLink(kind="else", target_id=else_block_id))

    cond_text = (condition.source_text if condition else "?").strip()
    if len(cond_text) > 40:
        cond_text = cond_text[:40] + "..."
    out.append(
        ScratchBlock(
            id=node.id,
            kind="if",
            label=f"решение: {cond_text}",
            ir_node_id=node.id,
            span=node.span,
            parent_id=parent_id,
            nest_level=nest,
            color=_KIND_COLORS["if"],
            links=tuple(links),
            source_snippet=_snippet(node),
            module_id=module_id,
            editable=True,
        )
    )
    for stmt in then_stmts:
        _emit_statement(stmt, node.id, nest + 1, out, module_id=module_id)
    if else_block_id is not None and else_body is not None:
        else_links: list[ScratchLink] = []
        if else_stmts:
            else_links.append(ScratchLink(kind="body", target_id=else_stmts[0].id))
            _append_next_chain(else_links, else_stmts)
        out.append(
            ScratchBlock(
                id=else_block_id,
                kind="else",
                label="иначе",
                ir_node_id=else_body.id,
                span=else_body.span,
                parent_id=node.id,
                nest_level=nest,
                color=_KIND_COLORS["else"],
                links=tuple(else_links),
                source_snippet=_snippet(else_body),
                module_id=module_id,
                editable=True,
            )
        )
        for stmt in else_stmts:
            _emit_statement(stmt, else_block_id, nest + 1, out, module_id=module_id)


def _emit_loop(
    node: IrNode,
    parent_id: str | None,
    nest: int,
    out: list[ScratchBlock],
    *,
    module_id: str | None,
) -> None:
    body = node.role_child(ROLE_BODY)
    stmts = _as_statements(body)
    kind_map = {
        IrNodeKind.WHILE: ("while", "цикл пока"),
        IrNodeKind.DO: ("do", "цикл делать пока"),
        IrNodeKind.FOR: ("for", "цикл для"),
        IrNodeKind.ENHANCED_FOR: ("foreach", "цикл для каждого"),
    }
    scratch_kind, prefix = kind_map[node.kind]
    condition = node.role_child(ROLE_CONDITION)
    hint = (condition.source_text if condition else node.source_text).strip()
    if len(hint) > 36:
        hint = hint[:36] + "..."
    links: list[ScratchLink] = []
    if stmts:
        links.append(ScratchLink(kind="body", target_id=stmts[0].id))
        _append_next_chain(links, stmts)
    out.append(
        ScratchBlock(
            id=node.id,
            kind=scratch_kind,
            label=f"{prefix} {hint}",
            ir_node_id=node.id,
            span=node.span,
            parent_id=parent_id,
            nest_level=nest,
            color=_KIND_COLORS[scratch_kind],
            links=tuple(links),
            source_snippet=_snippet(node),
            module_id=module_id,
            editable=True,
        )
    )
    for stmt in stmts:
        _emit_statement(stmt, node.id, nest + 1, out, module_id=module_id)


def _emit_try(
    node: IrNode,
    parent_id: str | None,
    nest: int,
    out: list[ScratchBlock],
    *,
    module_id: str | None,
) -> None:
    body = node.role_child(ROLE_BODY)
    stmts = _as_statements(body)
    catches = [c for c in node.children if c.kind == IrNodeKind.CATCH]
    finally_nodes = [c for c in node.children if c.kind == IrNodeKind.FINALLY]
    links: list[ScratchLink] = []
    if stmts:
        links.append(ScratchLink(kind="body", target_id=stmts[0].id))
        _append_next_chain(links, stmts)
    for catch in catches:
        links.append(ScratchLink(kind="children", target_id=catch.id))
    for fin in finally_nodes:
        links.append(ScratchLink(kind="children", target_id=fin.id))
    is_resources = node.kind == IrNodeKind.TRY_WITH_RESOURCES
    out.append(
        ScratchBlock(
            id=node.id,
            kind="try",
            label="попробовать с ресурсами" if is_resources else "попробовать",
            ir_node_id=node.id,
            span=node.span,
            parent_id=parent_id,
            nest_level=nest,
            color=_KIND_COLORS["try"],
            links=tuple(links),
            source_snippet=_snippet(node),
            module_id=module_id,
            editable=True,
        )
    )
    for stmt in stmts:
        _emit_statement(stmt, node.id, nest + 1, out, module_id=module_id)
    for catch in catches:
        catch_body = catch.role_child(ROLE_BODY)
        catch_stmts = _as_statements(catch_body)
        catch_links: list[ScratchLink] = []
        if catch_stmts:
            catch_links.append(ScratchLink(kind="body", target_id=catch_stmts[0].id))
            _append_next_chain(catch_links, catch_stmts)
        out.append(
            ScratchBlock(
                id=catch.id,
                kind="catch",
                label=f"поймать {catch.name or catch.type_text or 'исключение'}",
                ir_node_id=catch.id,
                span=catch.span,
                parent_id=node.id,
                nest_level=nest + 1,
                color=_KIND_COLORS["catch"],
                links=tuple(catch_links),
                source_snippet=_snippet(catch),
                module_id=module_id,
                editable=True,
            )
        )
        for stmt in catch_stmts:
            _emit_statement(stmt, catch.id, nest + 2, out, module_id=module_id)
    for fin in finally_nodes:
        fin_body = fin.role_child(ROLE_BODY) or (fin.children[0] if fin.children else None)
        fin_stmts = _as_statements(fin_body)
        fin_links: list[ScratchLink] = []
        if fin_stmts:
            fin_links.append(ScratchLink(kind="body", target_id=fin_stmts[0].id))
            _append_next_chain(fin_links, fin_stmts)
        out.append(
            ScratchBlock(
                id=fin.id,
                kind="finally",
                label="наконец",
                ir_node_id=fin.id,
                span=fin.span,
                parent_id=node.id,
                nest_level=nest + 1,
                color=_KIND_COLORS["finally"],
                links=tuple(fin_links),
                source_snippet=_snippet(fin),
                module_id=module_id,
                editable=True,
            )
        )
        for stmt in fin_stmts:
            _emit_statement(stmt, fin.id, nest + 2, out, module_id=module_id)


def _emit_switch(
    node: IrNode,
    parent_id: str | None,
    nest: int,
    out: list[ScratchBlock],
    *,
    module_id: str | None,
) -> None:
    condition = node.role_child(ROLE_CONDITION)
    groups = [child for child in node.children if child.kind == IrNodeKind.SWITCH_GROUP]
    cond_text = (condition.source_text if condition else "?").strip()
    if len(cond_text) > 36:
        cond_text = cond_text[:36] + "..."
    links: list[ScratchLink] = []
    if groups:
        links.append(ScratchLink(kind="body", target_id=groups[0].id))
        for group in groups:
            links.append(ScratchLink(kind="children", target_id=group.id))
        _append_next_chain(links, groups)
    out.append(
        ScratchBlock(
            id=node.id,
            kind="switch",
            label=f"выбор: {cond_text}",
            ir_node_id=node.id,
            span=node.span,
            parent_id=parent_id,
            nest_level=nest,
            color=_KIND_COLORS["switch"],
            links=tuple(links),
            source_snippet=_snippet(node),
            module_id=module_id,
            editable=True,
        )
    )
    for group in groups:
        # label-дети (LITERAL) пропускаем - в схеме остаётся заголовок case.
        stmts = [child for child in group.children if child.kind != IrNodeKind.LITERAL]
        case_links: list[ScratchLink] = []
        if stmts:
            case_links.append(ScratchLink(kind="body", target_id=stmts[0].id))
            _append_next_chain(case_links, stmts)
        label = (group.label or group.name or "case").strip()
        if len(label) > 40:
            label = label[:40] + "..."
        out.append(
            ScratchBlock(
                id=group.id,
                kind="case",
                label=label,
                ir_node_id=group.id,
                span=group.span,
                parent_id=node.id,
                nest_level=nest + 1,
                color=_KIND_COLORS["case"],
                links=tuple(case_links),
                source_snippet=_snippet(group),
                module_id=module_id,
                editable=True,
            )
        )
        for stmt in stmts:
            _emit_statement(stmt, group.id, nest + 2, out, module_id=module_id)


def _emit_synchronized(
    node: IrNode,
    parent_id: str | None,
    nest: int,
    out: list[ScratchBlock],
    *,
    module_id: str | None,
) -> None:
    lock = node.role_child(ROLE_CONDITION)
    body = node.role_child(ROLE_BODY)
    stmts = _as_statements(body)
    lock_text = (lock.source_text if lock else "monitor").strip()
    if len(lock_text) > 32:
        lock_text = lock_text[:32] + "..."
    links: list[ScratchLink] = []
    if stmts:
        links.append(ScratchLink(kind="body", target_id=stmts[0].id))
        _append_next_chain(links, stmts)
    out.append(
        ScratchBlock(
            id=node.id,
            kind="synchronized",
            label=f"синхронно: {lock_text}",
            ir_node_id=node.id,
            span=node.span,
            parent_id=parent_id,
            nest_level=nest,
            color=_KIND_COLORS["synchronized"],
            links=tuple(links),
            source_snippet=_snippet(node),
            module_id=module_id,
            editable=True,
        )
    )
    for stmt in stmts:
        _emit_statement(stmt, node.id, nest + 1, out, module_id=module_id)


def _emit_labeled(
    node: IrNode,
    parent_id: str | None,
    nest: int,
    out: list[ScratchBlock],
    *,
    module_id: str | None,
) -> None:
    body = node.role_child(ROLE_BODY)
    label = node.label or node.name or "label"
    links: list[ScratchLink] = []
    if body is not None:
        links.append(ScratchLink(kind="body", target_id=body.id))
    out.append(
        ScratchBlock(
            id=node.id,
            kind="labeled",
            label=f"метка: {label}",
            ir_node_id=node.id,
            span=node.span,
            parent_id=parent_id,
            nest_level=nest,
            color=_KIND_COLORS["labeled"],
            links=tuple(links),
            source_snippet=_snippet(node),
            module_id=module_id,
            editable=True,
        )
    )
    if body is not None:
        _emit_statement(body, node.id, nest + 1, out, module_id=module_id)


def _emit_generic(
    node: IrNode,
    parent_id: str | None,
    nest: int,
    out: list[ScratchBlock],
    role_hint: str | None,
    *,
    module_id: str | None,
) -> None:
    del role_hint
    kind, label = _label_for(node)
    out.append(
        ScratchBlock(
            id=node.id,
            kind=kind,
            label=label,
            ir_node_id=node.id,
            span=node.span,
            parent_id=parent_id,
            nest_level=nest,
            color=_KIND_COLORS.get(kind, "#52525b"),
            links=(),
            source_snippet=_snippet(node),
            module_id=module_id,
            editable=True,
        )
    )


def _label_for(node: IrNode) -> tuple[str, str]:
    text = " ".join(node.source_text.strip().split())
    if len(text) > 48:
        text = text[:48] + "..."
    mapping: dict[IrNodeKind, tuple[str, str]] = {
        IrNodeKind.LOCAL_VARIABLE: ("variable", f"данные: {node.name or text}"),
        IrNodeKind.FIELD: ("variable", f"данные поле: {node.name or text}"),
        IrNodeKind.ASSIGNMENT: ("assignment", f"процесс: {text}"),
        IrNodeKind.EXPRESSION_STATEMENT: ("expression", f"процесс: {text}" if text else "процесс"),
        IrNodeKind.METHOD_INVOCATION: ("call", f"предопределенный: {node.name or text}"),
        IrNodeKind.EXPLICIT_CONSTRUCTOR_INVOCATION: (
            "call",
            f"предопределенный: {node.name or text}",
        ),
        IrNodeKind.OBJECT_CREATION: ("call", f"предопределенный new: {text}"),
        IrNodeKind.LAMBDA: ("call", f"лямбда: {text}"),
        IrNodeKind.METHOD_REFERENCE: ("call", f"ссылка: {text}"),
        IrNodeKind.CLASS_LITERAL: ("expression", f"класс: {text}"),
        IrNodeKind.ENUM_CONSTANT: ("variable", f"enum: {node.name or text}"),
        IrNodeKind.COMPACT_CONSTRUCTOR: ("method", f"compact ctor {node.name or text}"),
        IrNodeKind.FIELD_ACCESS: ("expression", f"поле: {text}"),
        IrNodeKind.ARRAY_ACCESS: ("expression", f"массив: {text}"),
        IrNodeKind.ARRAY_CREATION: ("expression", f"new массив: {text}"),
        IrNodeKind.CAST: ("expression", f"приведение: {text}"),
        IrNodeKind.TERNARY: ("expression", f"тернарный: {text}"),
        IrNodeKind.INSTANCEOF: ("expression", f"instanceof: {text}"),
        IrNodeKind.RETURN: ("return", f"вернуть {text}"),
        IrNodeKind.BREAK: ("break", "прервать"),
        IrNodeKind.CONTINUE: ("continue", "продолжить"),
        IrNodeKind.THROW: ("throw", f"бросить {text}"),
        IrNodeKind.ASSERT: ("assert", f"assert: {text}"),
        IrNodeKind.YIELD: ("yield", f"yield: {text}"),
        IrNodeKind.UNSUPPORTED: ("unsupported", f"не поддержано: {node.reason or text}"),
    }
    if node.kind in mapping:
        return mapping[node.kind]
    return ("expression", text or node.kind.value)


def _snippet(node: IrNode, limit: int = 160) -> str:
    text = " ".join(node.source_text.strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def _statement_children(block: IrNode) -> list[IrNode]:
    return [
        child
        for child in block.children
        if child.kind in _STATEMENT_KINDS or child.kind == IrNodeKind.IF
    ]


def _as_statements(node: IrNode | None) -> list[IrNode]:
    if node is None:
        return []
    if node.kind == IrNodeKind.BLOCK:
        return _statement_children(node)
    return [node]


def _append_next_chain(links: list[ScratchLink], nodes: list[IrNode]) -> None:
    for index in range(len(nodes) - 1):
        links.append(ScratchLink(kind="next", target_id=nodes[index + 1].id))


def _ensure_next_link(out: list[ScratchBlock], source_id: str, target_id: str) -> None:
    """Добавляет next к блоку source_id, если его ещё нет."""
    for index, block in enumerate(out):
        if block.id != source_id:
            continue
        if any(link.kind == "next" for link in block.links):
            return
        out[index] = ScratchBlock(
            id=block.id,
            kind=block.kind,
            label=block.label,
            ir_node_id=block.ir_node_id,
            span=block.span,
            parent_id=block.parent_id,
            nest_level=block.nest_level,
            color=block.color,
            links=(*block.links, ScratchLink(kind="next", target_id=target_id)),
            source_snippet=block.source_snippet,
            module_id=block.module_id,
            editable=block.editable,
        )
        return
