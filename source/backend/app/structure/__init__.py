"""Структурные блоки поверх IR."""

from app.structure.blocks import build_structural_blocks
from app.structure.models import LinkKind, StructuralBlock, StructuralLink

__all__ = [
    "LinkKind",
    "StructuralBlock",
    "StructuralLink",
    "build_structural_blocks",
]
