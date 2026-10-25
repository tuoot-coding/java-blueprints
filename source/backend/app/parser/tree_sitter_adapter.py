"""Инкапсуляция Tree-sitter Java: разбор байтов и обход ERROR/missing узлов."""

from __future__ import annotations

from dataclasses import dataclass

import tree_sitter_java as ts_java
from tree_sitter import Language, Node, Parser, Tree

_JAVA_LANGUAGE = Language(ts_java.language())


@dataclass(frozen=True, slots=True)
class SyntaxProblem:
    """Сырая проблема синтаксиса до преобразования в API-диагностику."""

    kind: str
    start_byte: int
    end_byte: int
    node_type: str


@dataclass(frozen=True, slots=True)
class ParsedSyntaxTree:
    """Результат разбора на уровне адаптера."""

    tree: Tree
    source_bytes: bytes
    has_error: bool
    problems: tuple[SyntaxProblem, ...]


def create_java_parser() -> Parser:
    return Parser(_JAVA_LANGUAGE)


def parse_java_bytes(source_bytes: bytes, parser: Parser | None = None) -> ParsedSyntaxTree:
    """Строит синтаксическое дерево для UTF-8 байтов исходника."""
    active_parser = parser or create_java_parser()
    tree = active_parser.parse(source_bytes)
    problems = tuple(_collect_problems(tree.root_node))
    return ParsedSyntaxTree(
        tree=tree,
        source_bytes=source_bytes,
        has_error=tree.root_node.has_error or bool(problems),
        problems=problems,
    )


def _collect_problems(root: Node) -> list[SyntaxProblem]:
    problems: list[SyntaxProblem] = []
    seen: set[tuple[str, int, int]] = set()

    def visit(node: Node) -> None:
        kind: str | None = None
        if node.is_missing:
            kind = "missing"
        elif node.type == "ERROR":
            kind = "error"

        if kind is not None:
            key = (kind, node.start_byte, node.end_byte)
            if key not in seen:
                seen.add(key)
                problems.append(
                    SyntaxProblem(
                        kind=kind,
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                        node_type=node.type,
                    )
                )

        for child in node.children:
            visit(child)

    visit(root)
    return problems
