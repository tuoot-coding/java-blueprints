"""Покрытие IR под ТЗ: java.lang, I/O, коллекции, исключения."""

from __future__ import annotations

from app.ir.models import IrNodeKind
from app.ir.query import count_unsupported, find_method_by_name, list_methods, walk_ir
from app.structure.scratch import build_scratch_program
from tests.java_fixtures import ir_from_source, read_java_fixture


def test_tz_fixture_has_no_unsupported() -> None:
    source = read_java_fixture("tz_java_lang_io_collections.java")
    root = ir_from_source(source)
    assert count_unsupported(root) == 0
    assert not any(node.kind == IrNodeKind.UNSUPPORTED for node in walk_ir(root))


def test_tz_core_language_nodes_present() -> None:
    source = read_java_fixture("tz_java_lang_io_collections.java")
    root = ir_from_source(source)
    kinds = {node.kind for node in walk_ir(root)}
    assert IrNodeKind.INTERFACE in kinds
    assert IrNodeKind.CLASS in kinds
    assert IrNodeKind.FIELD in kinds
    assert IrNodeKind.METHOD in kinds
    assert IrNodeKind.CONSTRUCTOR in kinds
    assert IrNodeKind.IF in kinds
    assert IrNodeKind.WHILE in kinds
    assert IrNodeKind.TRY in kinds or IrNodeKind.TRY_WITH_RESOURCES in kinds
    assert IrNodeKind.TRY_WITH_RESOURCES in kinds
    assert IrNodeKind.CATCH in kinds
    assert IrNodeKind.FINALLY in kinds
    assert IrNodeKind.THROW in kinds
    assert IrNodeKind.CAST in kinds
    assert IrNodeKind.TERNARY in kinds
    assert IrNodeKind.INSTANCEOF in kinds
    assert IrNodeKind.ARRAY_ACCESS in kinds
    assert IrNodeKind.ARRAY_CREATION in kinds
    assert IrNodeKind.FIELD_ACCESS in kinds
    assert IrNodeKind.METHOD_INVOCATION in kinds
    assert IrNodeKind.OBJECT_CREATION in kinds


def test_tz_io_and_collections_via_invocations() -> None:
    source = read_java_fixture("tz_java_lang_io_collections.java")
    root = ir_from_source(source)
    texts = " ".join(node.source_text for node in walk_ir(root) if node.kind == IrNodeKind.METHOD_INVOCATION)
    assert "println" in texts or "printf" in texts
    creations = [
        node.type_text or ""
        for node in walk_ir(root)
        if node.kind == IrNodeKind.OBJECT_CREATION
    ]
    joined = " ".join(creations)
    assert "Scanner" in joined
    assert "ArrayList" in joined or "HashMap" in joined


def test_tz_custom_exception_and_throws() -> None:
    source = read_java_fixture("tz_java_lang_io_collections.java")
    root = ir_from_source(source)
    may_fail = find_method_by_name(root, "mayFail")
    assert may_fail is not None
    assert may_fail.throws_text is not None
    assert "DomainError" in may_fail.throws_text
    classes = [node.name for node in walk_ir(root) if node.kind == IrNodeKind.CLASS]
    assert "DomainError" in classes
    assert "TzCoverage" in classes


def test_tz_interface_methods_listed() -> None:
    source = read_java_fixture("tz_java_lang_io_collections.java")
    root = ir_from_source(source)
    names = [method.name for method in list_methods(root)]
    assert "mark" in names
    assert "hint" in names
    assert "main" in names


def test_tz_scratch_builds_without_unsupported_blocks() -> None:
    source = read_java_fixture("tz_java_lang_io_collections.java")
    root = ir_from_source(source)
    program = build_scratch_program(root)
    assert len(program.blocks) > 10
    assert not any(block.kind == "unsupported" for block in program.blocks)


def test_expression_constructs_roundtrip_kinds() -> None:
    source = """
public class E {
  int m(Object o, int[] a) {
    int x = a[0];
    int[] b = new int[2];
    String s = (String) o;
    boolean ok = o instanceof String;
    return ok ? x : b[1];
  }
}
"""
    root = ir_from_source(source)
    assert count_unsupported(root) == 0
    kinds = {node.kind for node in walk_ir(root)}
    assert IrNodeKind.ARRAY_ACCESS in kinds
    assert IrNodeKind.ARRAY_CREATION in kinds
    assert IrNodeKind.CAST in kinds
    assert IrNodeKind.INSTANCEOF in kinds
    assert IrNodeKind.TERNARY in kinds
