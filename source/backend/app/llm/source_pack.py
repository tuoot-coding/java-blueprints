"""Упаковка исходника для LLM: логический контур + код; поддержка файлов >1000 строк."""

from __future__ import annotations

from dataclasses import dataclass

from app.ir.models import IrNode, IrNodeKind
from app.ir.query import list_methods
from app.llm.logic_outline import LogicOutline, build_logic_outline


@dataclass(frozen=True, slots=True)
class LlmSourcePack:
    """Текст, который уходит в LLM, и метаданные об усечении."""

    payload_text: str
    mode: str
    original_chars: int
    payload_chars: int
    truncated: bool
    included_methods: tuple[str, ...]
    logic_outline: str
    control_nodes: int
    line_count: int = 0


# DeepSeek context большой: полный исходник до ~80 КБ символов.
FULL_SOURCE_CHAR_LIMIT = 80_000
MAX_CODE_CHARS = 100_000
MAX_PACK_CHARS = 120_000
MAX_FULL_METHODS = 24
MAX_METHOD_BODY_CHARS = 8_000
# Порог «крупный файл» для repair через replacements.
REPAIR_FULL_CHAR_LIMIT = 48_000
REPAIR_FULL_LINE_LIMIT = 1_200


def build_llm_source_pack(source: str, ir_root: IrNode) -> LlmSourcePack:
    """Всегда включает логический контур; код - полностью или выборочно по приоритету."""
    original = len(source)
    line_count = source.count("\n") + (1 if source else 0)
    outline = build_logic_outline(ir_root)
    methods = list_methods(ir_root)
    method_names = tuple(method.name or "?" for method in methods if method.name)

    if original <= FULL_SOURCE_CHAR_LIMIT:
        payload = _compose_payload(outline, "SOURCE_FULL", source)
        clamped = _clamp_pack(payload)
        return LlmSourcePack(
            payload_text=clamped,
            mode="logic_plus_full",
            original_chars=original,
            payload_chars=len(clamped),
            truncated=outline.truncated or len(payload) > MAX_PACK_CHARS,
            included_methods=method_names,
            logic_outline=outline.text,
            control_nodes=outline.control_nodes,
            line_count=line_count,
        )

    ranked = sorted(methods, key=_method_priority, reverse=True)
    selected = ranked[:MAX_FULL_METHODS]
    outline_lines = [
        f"- {method.name or '?'} L{method.span.start_line}-{method.span.end_line} "
        f"c={len(method.source_text)}"
        for method in methods[:200]
    ]
    code_parts: list[str] = [
        f"SOURCE_TRUNCATED chars={original} lines={line_count}",
        "METHOD_INDEX:",
        *outline_lines,
        "",
        "HOT_METHODS:",
    ]
    included: list[str] = []
    for method in selected:
        name = method.name or "?"
        included.append(name)
        body = method.source_text
        if len(body) > MAX_METHOD_BODY_CHARS:
            body = body[:MAX_METHOD_BODY_CHARS] + "\n/* truncated */\n"
        code_parts.append(f"// {name} L{method.span.start_line}-{method.span.end_line}")
        code_parts.append(body)
        code_parts.append("")
        if sum(len(part) for part in code_parts) > MAX_CODE_CHARS:
            code_parts.append("/* methods omitted */")
            break

    code_block = "\n".join(code_parts)
    if len(code_block) > MAX_CODE_CHARS:
        code_block = code_block[:MAX_CODE_CHARS] + "\n/* pack truncated */\n"
    payload = _compose_payload(outline, "SOURCE_SELECTIVE", code_block)
    clamped = _clamp_pack(payload)
    return LlmSourcePack(
        payload_text=clamped,
        mode="logic_plus_hotspots",
        original_chars=original,
        payload_chars=len(clamped),
        truncated=True,
        included_methods=tuple(included),
        logic_outline=outline.text,
        control_nodes=outline.control_nodes,
        line_count=line_count,
    )


def build_repair_source_pack(source: str, ir_root: IrNode) -> LlmSourcePack:
    """Пакет для исправления: полный файл, если влезает; иначе hotspots + replacements."""
    original = len(source)
    line_count = source.count("\n") + (1 if source else 0)
    outline = build_logic_outline(ir_root)
    methods = list_methods(ir_root)
    method_names = tuple(method.name or "?" for method in methods if method.name)

    if original <= REPAIR_FULL_CHAR_LIMIT and line_count <= REPAIR_FULL_LINE_LIMIT:
        payload = _compose_payload(outline, "SOURCE_FULL_REPAIR", source)
        clamped = _clamp_pack(payload)
        return LlmSourcePack(
            payload_text=clamped,
            mode="repair_full",
            original_chars=original,
            payload_chars=len(clamped),
            truncated=outline.truncated or len(payload) > MAX_PACK_CHARS,
            included_methods=method_names,
            logic_outline=outline.text,
            control_nodes=outline.control_nodes,
            line_count=line_count,
        )
    return build_llm_source_pack(source, ir_root)


def prefer_repair_replacements(pack: LlmSourcePack) -> bool:
    """Крупные файлы надёжнее править точечными replacements."""
    return (
        pack.truncated
        or pack.mode != "repair_full"
        or pack.original_chars > REPAIR_FULL_CHAR_LIMIT
        or pack.line_count > REPAIR_FULL_LINE_LIMIT
    )


def _compose_payload(outline: LogicOutline, code_tag: str, code: str) -> str:
    return (
        "LOGIC_OUTLINE:\n"
        f"{outline.text}\n"
        f"\n{code_tag}:\n"
        f"{code}"
    )


def _clamp_pack(payload: str) -> str:
    if len(payload) <= MAX_PACK_CHARS:
        return payload
    return payload[: MAX_PACK_CHARS - 18] + "\n/* pack cut */\n"


def _method_priority(method: IrNode) -> int:
    score = len(method.source_text)
    score += 800 * _count_kinds(method, IrNodeKind.FOR)
    score += 800 * _count_kinds(method, IrNodeKind.WHILE)
    score += 800 * _count_kinds(method, IrNodeKind.DO)
    score += 600 * _count_kinds(method, IrNodeKind.ENHANCED_FOR)
    score += 400 * _count_kinds(method, IrNodeKind.IF)
    score += 500 * _count_kinds(method, IrNodeKind.TRY)
    return score


def _count_kinds(node: IrNode, kind: IrNodeKind) -> int:
    total = 1 if node.kind == kind else 0
    for child in node.children:
        total += _count_kinds(child, kind)
    return total
