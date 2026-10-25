"""Компактный логический контур IR для LLM: управление потоком без полного AST."""

from __future__ import annotations

from dataclasses import dataclass

from app.ir.models import (
    ROLE_BODY,
    ROLE_CONDITION,
    ROLE_ELSE,
    ROLE_PARAMETERS,
    IrNode,
    IrNodeKind,
)
from app.ir.query import list_methods, summarize_ir

# Жесткий потолок символов контура в одном LLM-пакете.
MAX_OUTLINE_CHARS = 8_000
# Сколько методов включать с телом контура.
MAX_OUTLINE_METHODS = 24
# Глубина вложенности управляющих конструкций в контуре.
MAX_OUTLINE_DEPTH = 8


@dataclass(frozen=True, slots=True)
class LogicOutline:
    """Текстовый снимок логики: методы, ветвления, циклы, выходы."""

    text: str
    method_count: int
    control_nodes: int
    truncated: bool


def build_logic_outline(ir_root: IrNode) -> LogicOutline:
    """Строит лаконичный контур логики по структурному IR (не сырой синтаксис)."""
    summary = summarize_ir(ir_root)
    methods = list_methods(ir_root)
    lines: list[str] = [
        f"classes={','.join(summary.class_names) or '-'}",
        f"methods={len(methods)} unsupported={summary.unsupported_count}",
    ]
    control_nodes = 0
    truncated = False
    for index, method in enumerate(methods):
        if index >= MAX_OUTLINE_METHODS:
            truncated = True
            lines.append(f"... +{len(methods) - MAX_OUTLINE_METHODS} methods omitted")
            break
        params = ", ".join(
            (p.name or p.type_text or "?") for p in method.role_children(ROLE_PARAMETERS)
        )
        sig = f"{method.name or '?'}({params})"
        lines.append(f"{sig} L{method.span.start_line}-{method.span.end_line}")
        body = method.role_child(ROLE_BODY)
        if body is None:
            continue
        body_lines, body_controls, body_trunc = _outline_block(body, depth=1)
        control_nodes += body_controls
        lines.extend(body_lines)
        if body_trunc:
            truncated = True
        if sum(len(line) + 1 for line in lines) > MAX_OUTLINE_CHARS:
            truncated = True
            lines.append("... outline truncated")
            break

    text = "\n".join(lines)
    if len(text) > MAX_OUTLINE_CHARS:
        text = text[: MAX_OUTLINE_CHARS - 20] + "\n... outline truncated"
        truncated = True
    return LogicOutline(
        text=text,
        method_count=len(methods),
        control_nodes=control_nodes,
        truncated=truncated,
    )


def _outline_block(node: IrNode, *, depth: int) -> tuple[list[str], int, bool]:
    if depth > MAX_OUTLINE_DEPTH:
        return ([f"{_indent(depth)}... nest truncated"], 0, True)
    lines: list[str] = []
    controls = 0
    truncated = False
    for child in _statement_children(node):
        child_lines, child_controls, child_trunc = _outline_statement(child, depth=depth)
        lines.extend(child_lines)
        controls += child_controls
        if child_trunc:
            truncated = True
        if sum(len(line) + 1 for line in lines) > MAX_OUTLINE_CHARS // 2:
            truncated = True
            lines.append(f"{_indent(depth)}...")
            break
    return lines, controls, truncated


def _outline_statement(node: IrNode, *, depth: int) -> tuple[list[str], int, bool]:
    indent = _indent(depth)
    span = f"L{node.span.start_line}"
    if node.kind == IrNodeKind.IF:
        cond = _cond_preview(node)
        lines = [f"{indent}if ({cond}) {span}"]
        controls = 1
        truncated = False
        body = node.role_child(ROLE_BODY)
        if body is not None:
            body_lines, body_c, body_t = _outline_block(body, depth=depth + 1)
            lines.extend(body_lines)
            controls += body_c
            truncated = truncated or body_t
        else_node = node.role_child(ROLE_ELSE)
        if else_node is not None:
            lines.append(f"{indent}else")
            if else_node.kind == IrNodeKind.IF:
                else_lines, else_c, else_t = _outline_statement(else_node, depth=depth)
                # else if: убираем лишний indent у вложенного if
                lines.extend(else_lines)
                controls += else_c
                truncated = truncated or else_t
            else:
                else_lines, else_c, else_t = _outline_block(else_node, depth=depth + 1)
                lines.extend(else_lines)
                controls += else_c
                truncated = truncated or else_t
        return lines, controls, truncated

    if node.kind in {IrNodeKind.WHILE, IrNodeKind.DO, IrNodeKind.FOR, IrNodeKind.ENHANCED_FOR}:
        kind = {
            IrNodeKind.WHILE: "while",
            IrNodeKind.DO: "do",
            IrNodeKind.FOR: "for",
            IrNodeKind.ENHANCED_FOR: "foreach",
        }[node.kind]
        cond = _cond_preview(node)
        lines = [f"{indent}{kind} ({cond}) {span}"]
        body = node.role_child(ROLE_BODY)
        controls = 1
        truncated = False
        if body is not None:
            body_lines, body_c, body_t = _outline_block(body, depth=depth + 1)
            lines.extend(body_lines)
            controls += body_c
            truncated = body_t
        return lines, controls, truncated

    if node.kind == IrNodeKind.TRY:
        lines = [f"{indent}try {span}"]
        controls = 1
        truncated = False
        body = node.role_child(ROLE_BODY)
        if body is not None:
            body_lines, body_c, body_t = _outline_block(body, depth=depth + 1)
            lines.extend(body_lines)
            controls += body_c
            truncated = body_t
        for child, role in zip(node.children, node.child_roles, strict=True):
            if role == "catch":
                lines.append(f"{indent}catch {child.name or ''} {span}")
                catch_body = child.role_child(ROLE_BODY)
                if catch_body is not None:
                    c_lines, c_c, c_t = _outline_block(catch_body, depth=depth + 1)
                    lines.extend(c_lines)
                    controls += c_c + 1
                    truncated = truncated or c_t
            elif role == "finally":
                lines.append(f"{indent}finally")
                fin_body = child.role_child(ROLE_BODY) or child
                f_lines, f_c, f_t = _outline_block(fin_body, depth=depth + 1)
                lines.extend(f_lines)
                controls += f_c + 1
                truncated = truncated or f_t
        return lines, controls, truncated

    if node.kind == IrNodeKind.RETURN:
        return [f"{indent}return {_short(node.source_text, 48)} {span}"], 0, False
    if node.kind == IrNodeKind.THROW:
        return [f"{indent}throw {_short(node.source_text, 48)} {span}"], 0, False
    if node.kind in {IrNodeKind.BREAK, IrNodeKind.CONTINUE}:
        return [f"{indent}{node.kind.value.replace('_statement', '')} {span}"], 0, False
    if node.kind == IrNodeKind.LOCAL_VARIABLE:
        return [f"{indent}var {_short(node.source_text, 56)} {span}"], 0, False
    if node.kind == IrNodeKind.UNSUPPORTED:
        return [f"{indent}unsupported:{node.syntax_type} {span}"], 0, False
    if node.kind == IrNodeKind.BLOCK:
        return _outline_block(node, depth=depth)

    preview = _short(node.source_text.replace("\n", " "), 56)
    return [f"{indent}{_kind_label(node)} {preview} {span}"], 0, False


def _statement_children(node: IrNode) -> list[IrNode]:
    if node.kind == IrNodeKind.BLOCK:
        return [
            child
            for child in node.children
            if child.kind
            not in {
                IrNodeKind.COMMENT,
                IrNodeKind.IDENTIFIER,
                IrNodeKind.LITERAL,
            }
        ]
    return [node]


def _cond_preview(node: IrNode) -> str:
    cond = node.role_child(ROLE_CONDITION)
    if cond is None:
        return "?"
    return _short(cond.source_text.replace("\n", " "), 40)


def _kind_label(node: IrNode) -> str:
    mapping = {
        IrNodeKind.ASSIGNMENT: "assign",
        IrNodeKind.EXPRESSION_STATEMENT: "expr",
        IrNodeKind.METHOD_INVOCATION: "call",
        IrNodeKind.OBJECT_CREATION: "new",
    }
    return mapping.get(node.kind, node.kind.value)


def _short(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "..."


def _indent(depth: int) -> str:
    return "  " * depth
