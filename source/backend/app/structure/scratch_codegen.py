"""Детерминированная сборка Java из модульной схемы (без LLM).

Существующие блоки берутся по UTF-8 span из исходника. Новые user_* - из
source_snippet. Порядок операторов - next-цепочка от start. Тело составных
конструкций пересобирается, если внутри были вставки/удаления/перестановки.
"""

from __future__ import annotations

from app.structure.scratch import ScratchBlock, ScratchProgram

_SKIP_KINDS = frozenset(
    {
        "start",
        "end",
        "parameter",
        "class",
        "interface",
        "enum",
        "record",
        "method",
        "else",
    }
)
_CONTAINER_KINDS = frozenset(
    {"if", "while", "do", "for", "foreach", "try", "switch", "synchronized", "labeled"}
)


def apply_scratch_to_source(source: str, program: ScratchProgram) -> str:
    """Переписывает тела методов по схеме. Неизменённые методы сохраняются как есть."""
    source_bytes = source.encode("utf-8")
    methods = [block for block in program.blocks if block.kind == "method"]
    # С конца к началу, чтобы байтовые смещения оставались валидными.
    methods_sorted = sorted(methods, key=lambda item: item.span.start_byte, reverse=True)
    result = source_bytes
    for method in methods_sorted:
        body_range = _method_body_interior(result, method)
        if body_range is None:
            continue
        body_start, body_end = body_range
        stmt_indent = _detect_statement_indent(result, body_start, body_end)
        rendered = _render_method_body(program, method, source_bytes, stmt_indent)
        if rendered is None:
            continue
        old_interior = result[body_start:body_end].decode("utf-8")
        if _ws_norm(rendered) == _ws_norm(old_interior):
            # Нет смысловых правок - сохраняем исходные байты тела.
            continue
        close_indent = _line_indent_at(result, body_end)
        if rendered:
            new_interior = b"\n" + rendered.encode("utf-8") + b"\n" + close_indent.encode("utf-8")
        else:
            new_interior = b"\n" + close_indent.encode("utf-8")
        result = result[:body_start] + new_interior + result[body_end:]
    return result.decode("utf-8")


def _render_method_body(
    program: ScratchProgram,
    method: ScratchBlock,
    original_bytes: bytes,
    indent: str,
) -> str | None:
    start = _find_start(program, method.id)
    if start is None:
        return None
    first_id = _link_target(start, "next")
    statements = _follow_next_chain(program, first_id)
    lines: list[str] = []
    for statement in statements:
        if statement.kind in _SKIP_KINDS:
            continue
        text = _render_statement(program, statement, original_bytes, indent)
        if text.strip():
            lines.append(text)
    return "\n".join(lines)


def _render_statement(
    program: ScratchProgram,
    block: ScratchBlock,
    original_bytes: bytes,
    indent: str,
) -> str:
    body_children = _body_chain(program, block)
    else_block = _else_block(program, block)
    else_children = _body_chain(program, else_block) if else_block else []
    structurally_changed = _structure_changed(block, body_children, else_children)

    if not structurally_changed and _has_span(block) and not block.id.startswith("user_"):
        raw = _slice_bytes(original_bytes, block.span.start_byte, block.span.end_byte)
        return _reindent_block(raw.strip("\r\n"), indent)

    if block.kind in _CONTAINER_KINDS or body_children or else_block:
        return _render_container(
            program,
            block,
            body_children,
            else_block,
            else_children,
            original_bytes,
            indent,
        )

    snippet = (block.source_snippet or "").strip()
    if not snippet and _has_span(block):
        snippet = _slice_bytes(original_bytes, block.span.start_byte, block.span.end_byte).strip()
    if not snippet:
        snippet = _fallback_snippet(block)
    return _reindent_block(snippet, indent)


def _render_container(
    program: ScratchProgram,
    block: ScratchBlock,
    body_children: list[ScratchBlock],
    else_block: ScratchBlock | None,
    else_children: list[ScratchBlock],
    original_bytes: bytes,
    indent: str,
) -> str:
    header = _container_header(block, original_bytes)
    child_indent = indent + "    "
    body_lines = [
        _render_statement(program, child, original_bytes, child_indent)
        for child in body_children
        if child.kind not in _SKIP_KINDS
    ]
    body_text = "\n".join(line for line in body_lines if line.strip())
    parts = [f"{indent}{header}", body_text if body_text else f"{child_indent}", f"{indent}}}"]
    if else_block is not None or block.kind == "if":
        else_header = "else {"
        if else_block is not None and _has_span(else_block):
            else_raw = _slice_bytes(
                original_bytes, else_block.span.start_byte, else_block.span.end_byte
            ).strip()
            if else_raw.startswith("else"):
                # Полный else {...} из исходника, если дети не менялись.
                if not _structure_changed(else_block, else_children, []):
                    return "\n".join(
                        [
                            f"{indent}{header}",
                            body_text if body_text else f"{child_indent}",
                            f"{indent}}}",
                            _reindent_block(else_raw, indent),
                        ]
                    )
        else_lines = [
            _render_statement(program, child, original_bytes, child_indent)
            for child in else_children
            if child.kind not in _SKIP_KINDS
        ]
        else_text = "\n".join(line for line in else_lines if line.strip())
        if else_block is not None or else_text:
            parts.extend(
                [
                    f"{indent}{else_header}",
                    else_text if else_text else f"{child_indent}",
                    f"{indent}}}",
                ]
            )
    return "\n".join(parts)


def _container_header(block: ScratchBlock, original_bytes: bytes) -> str:
    if _has_span(block):
        raw = _slice_bytes(original_bytes, block.span.start_byte, block.span.end_byte)
        header = _extract_open_header(raw)
        if header:
            return header
    snippet = (block.source_snippet or "").strip()
    if snippet:
        header = _extract_open_header(snippet)
        if header:
            return header
    return _fallback_header(block)


def _extract_open_header(text: str) -> str:
    """Текст до первой открывающей скобки тела включительно."""
    depth_paren = 0
    for index, char in enumerate(text):
        if char == "(":
            depth_paren += 1
        elif char == ")":
            depth_paren = max(0, depth_paren - 1)
        elif char == "{" and depth_paren == 0:
            return text[: index + 1].strip()
    # Нет тела-скобки: однострочный оператор.
    return text.strip()


def _fallback_header(block: ScratchBlock) -> str:
    label = block.label.split(":", 1)[-1].strip() if ":" in block.label else block.label
    kind = block.kind
    if kind == "if":
        return f"if ({label or 'condition'}) {{"
    if kind == "while":
        return f"while ({label or 'condition'}) {{"
    if kind == "do":
        return "do {"
    if kind in {"for", "foreach"}:
        return f"for ({label or '...'}) {{"
    if kind == "try":
        return "try {"
    if kind == "switch":
        return f"switch ({label or 'value'}) {{"
    if kind == "synchronized":
        return f"synchronized ({label or 'this'}) {{"
    return f"{kind} {{"


def _fallback_snippet(block: ScratchBlock) -> str:
    kind = block.kind
    if kind == "return":
        return "return;"
    if kind == "break":
        return "break;"
    if kind == "continue":
        return "continue;"
    if block.source_snippet:
        return block.source_snippet.strip()
    return f"/* {block.label} */;"


def _structure_changed(
    block: ScratchBlock,
    body_children: list[ScratchBlock],
    else_children: list[ScratchBlock],
) -> bool:
    if block.id.startswith("user_"):
        return True
    for child in [*body_children, *else_children]:
        if child.id.startswith("user_"):
            return True
        if not _has_span(child):
            return True
    # Если у контейнера есть body-связь, но детей нет - возможно удалили все.
    has_body_link = _link_target(block, "body") is not None
    if has_body_link and not body_children and block.kind in _CONTAINER_KINDS:
        return True
    return False


def _body_chain(program: ScratchProgram, block: ScratchBlock | None) -> list[ScratchBlock]:
    if block is None:
        return []
    children = [
        item
        for item in program.blocks
        if item.parent_id == block.id and item.kind not in _SKIP_KINDS
    ]
    if not children:
        return []
    child_ids = {item.id for item in children}
    by_id = {item.id: item for item in children}

    # Вариант A: body + next на самом контейнере (как в IR для if/loop).
    ordered_ids: list[str] = []
    first = _link_target(block, "body")
    if first and first in child_ids:
        ordered_ids.append(first)
        for link in block.links:
            if (
                link.kind == "next"
                and link.target_id in child_ids
                and link.target_id not in ordered_ids
            ):
                ordered_ids.append(link.target_id)

    # Вариант B: next на самих детях (после правок schemeEdit).
    if len(ordered_ids) <= 1:
        from_children = _ordered_children(program, block.id)
        if from_children:
            return [item for item in from_children if item.kind not in _SKIP_KINDS]

    if not ordered_ids and first and first in by_id:
        return [
            item
            for item in _follow_next_chain(program, first)
            if item.id in child_ids and item.kind not in _SKIP_KINDS
        ]

    result = [by_id[item_id] for item_id in ordered_ids if item_id in by_id]
    seen = {item.id for item in result}
    for item in children:
        if item.id not in seen:
            result.append(item)
    return result


def _else_block(program: ScratchProgram, block: ScratchBlock) -> ScratchBlock | None:
    else_id = _link_target(block, "else")
    if else_id is None:
        return None
    return _by_id(program, else_id)


def _ordered_children(program: ScratchProgram, parent_id: str) -> list[ScratchBlock]:
    children = [block for block in program.blocks if block.parent_id == parent_id]
    if not children:
        return []
    by_id = {block.id: block for block in children}
    targets = {
        link.target_id
        for block in children
        for link in block.links
        if link.kind == "next"
    }
    starts = [block for block in children if block.id not in targets]
    ordered: list[ScratchBlock] = []
    seen: set[str] = set()
    for start in starts or children[:1]:
        current: ScratchBlock | None = start
        while current is not None and current.id not in seen:
            seen.add(current.id)
            ordered.append(current)
            next_id = _link_target(current, "next")
            current = by_id.get(next_id) if next_id else None
    for block in children:
        if block.id not in seen:
            ordered.append(block)
    return ordered


def _follow_next_chain(program: ScratchProgram, first_id: str | None) -> list[ScratchBlock]:
    if not first_id:
        return []
    ordered: list[ScratchBlock] = []
    seen: set[str] = set()
    current_id: str | None = first_id
    while current_id and current_id not in seen:
        seen.add(current_id)
        block = _by_id(program, current_id)
        if block is None or block.kind == "end":
            break
        ordered.append(block)
        current_id = _link_target(block, "next")
    return ordered


def _find_start(program: ScratchProgram, method_id: str) -> ScratchBlock | None:
    for block in program.blocks:
        if block.kind == "start" and block.parent_id == method_id:
            return block
    method = _by_id(program, method_id)
    if method is None:
        return None
    start_id = _link_target(method, "body")
    return _by_id(program, start_id) if start_id else None


def _method_body_interior(source_bytes: bytes, method: ScratchBlock) -> tuple[int, int] | None:
    if not _has_span(method):
        return None
    start = method.span.start_byte
    end = method.span.end_byte
    if end <= start or end > len(source_bytes):
        return None
    chunk = source_bytes[start:end]
    open_rel = _find_body_open_brace(chunk)
    if open_rel is None:
        return None
    close_rel = _find_matching_brace(chunk, open_rel)
    if close_rel is None:
        return None
    return start + open_rel + 1, start + close_rel


def _find_body_open_brace(chunk: bytes) -> int | None:
    depth_paren = 0
    in_str = False
    in_char = False
    escape = False
    i = 0
    while i < len(chunk):
        ch = chunk[i]
        if in_str:
            if escape:
                escape = False
            elif ch == 0x5C:  # \
                escape = True
            elif ch == 0x22:  # "
                in_str = False
            i += 1
            continue
        if in_char:
            if escape:
                escape = False
            elif ch == 0x5C:
                escape = True
            elif ch == 0x27:  # '
                in_char = False
            i += 1
            continue
        if ch == 0x22:
            in_str = True
        elif ch == 0x27:
            in_char = True
        elif ch == 0x28:  # (
            depth_paren += 1
        elif ch == 0x29:  # )
            depth_paren = max(0, depth_paren - 1)
        elif ch == 0x7B and depth_paren == 0:  # {
            return i
        i += 1
    return None


def _find_matching_brace(chunk: bytes, open_index: int) -> int | None:
    depth = 0
    in_str = False
    in_char = False
    escape = False
    for i in range(open_index, len(chunk)):
        ch = chunk[i]
        if in_str:
            if escape:
                escape = False
            elif ch == 0x5C:
                escape = True
            elif ch == 0x22:
                in_str = False
            continue
        if in_char:
            if escape:
                escape = False
            elif ch == 0x5C:
                escape = True
            elif ch == 0x27:
                in_char = False
            continue
        if ch == 0x22:
            in_str = True
        elif ch == 0x27:
            in_char = True
        elif ch == 0x7B:
            depth += 1
        elif ch == 0x7D:
            depth -= 1
            if depth == 0:
                return i
    return None


def _detect_statement_indent(source_bytes: bytes, body_start: int, body_end: int) -> str:
    """Берёт отступ первой непустой строки тела метода."""
    interior = source_bytes[body_start:body_end]
    for raw_line in interior.split(b"\n"):
        if not raw_line.strip():
            continue
        indent_chars: list[str] = []
        for ch in raw_line:
            if ch in (0x20, 0x09):
                indent_chars.append(chr(ch))
            else:
                break
        if indent_chars:
            return "".join(indent_chars)
        break
    close_indent = _line_indent_at(source_bytes, body_end)
    return close_indent + "    "


def _ws_norm(text: str) -> str:
    return " ".join(text.split())


def _line_indent_at(source_bytes: bytes, position: int) -> str:
    line_start = source_bytes.rfind(b"\n", 0, position) + 1
    line = source_bytes[line_start:position]
    indent_chars: list[str] = []
    for ch in line:
        if ch in (0x20, 0x09):
            indent_chars.append(chr(ch))
        else:
            break
    return "".join(indent_chars)


def _reindent_block(text: str, indent: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines:
        return indent
    # Span часто без ведущего отступа первой строки, но с абсолютными
    # отступами продолжения - база = min отступа хвоста, если первая = 0.
    content_indents = [
        len(line) - len(line.lstrip(" \t")) for line in lines if line.strip()
    ]
    if not content_indents:
        return indent
    first_indent = content_indents[0]
    if first_indent == 0 and len(content_indents) > 1:
        base = min(content_indents[1:])
    else:
        base = first_indent
    out: list[str] = []
    for line in lines:
        if not line.strip():
            out.append("")
            continue
        current = len(line) - len(line.lstrip(" \t"))
        rel = max(0, current - base)
        out.append(indent + (" " * rel) + line.lstrip(" \t"))
    return "\n".join(out)


def _has_span(block: ScratchBlock) -> bool:
    return block.span.end_byte > block.span.start_byte


def _slice_bytes(data: bytes, start: int, end: int) -> str:
    start = max(0, min(start, len(data)))
    end = max(start, min(end, len(data)))
    return data[start:end].decode("utf-8")


def _by_id(program: ScratchProgram, block_id: str | None) -> ScratchBlock | None:
    if not block_id:
        return None
    for block in program.blocks:
        if block.id == block_id:
            return block
    return None


def _link_target(block: ScratchBlock, kind: str) -> str | None:
    for link in block.links:
        if link.kind == kind:
            return link.target_id
    return None
