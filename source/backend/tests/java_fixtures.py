"""Чтение Java-фикстур из fixtures/java."""

from __future__ import annotations

from pathlib import Path

from app.ir.builder import build_structural_ir
from app.ir.models import IrNode
from app.parser.service import inspect_java_source

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "java"


def read_java_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def ir_from_source(source: str) -> IrNode:
    inspection = inspect_java_source(source)
    return build_structural_ir(source, inspection.tree)
