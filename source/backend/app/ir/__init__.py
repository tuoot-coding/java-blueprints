"""Структурное промежуточное представление Java."""

from app.ir.builder import build_structural_ir
from app.ir.models import IrNode, IrNodeKind, SourceSpan
from app.ir.query import find_method_by_name, list_methods, summarize_ir, walk_ir

__all__ = [
    "IrNode",
    "IrNodeKind",
    "SourceSpan",
    "build_structural_ir",
    "find_method_by_name",
    "list_methods",
    "summarize_ir",
    "walk_ir",
]
