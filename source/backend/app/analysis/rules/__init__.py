"""Правила статического анализа по IR."""

from app.analysis.rules.bloat import find_bloat
from app.analysis.rules.complexity import find_complexity, method_metrics
from app.analysis.rules.empty_blocks import find_empty_blocks
from app.analysis.rules.unreachable import find_unreachable
from app.analysis.rules.unsupported import find_unsupported

__all__ = [
    "find_bloat",
    "find_complexity",
    "find_empty_blocks",
    "find_unreachable",
    "find_unsupported",
    "method_metrics",
]
