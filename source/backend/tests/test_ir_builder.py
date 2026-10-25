from __future__ import annotations

from app.ir.models import IrNodeKind
from app.ir.query import find_method_by_name, list_methods, walk_ir
from app.parser.positions import LineIndex
from tests.java_fixtures import ir_from_source, read_java_fixture


def test_simple_method_ir_keeps_parameters_and_binary() -> None:
    source = read_java_fixture("simple_method.java")
    root = ir_from_source(source)
    method = find_method_by_name(root, "add")

    assert root.kind == IrNodeKind.COMPILATION_UNIT
    assert method is not None
    assert method.kind == IrNodeKind.METHOD
    assert method.type_text == "int"
    assert [item.name for item in method.role_children("parameters")] == ["left", "right"]
    returned = method.role_child("body")
    assert returned is not None
    return_node = returned.children[0]
    assert return_node.kind == IrNodeKind.RETURN
    binary = return_node.role_child("value")
    assert binary is not None
    assert binary.kind == IrNodeKind.BINARY
    assert binary.operator == "+"
    left = binary.role_child("left")
    assert left is not None
    assert left.name == "left"


def test_ir_slices_match_source_and_line_index() -> None:
    source = read_java_fixture("cyrillic.java")
    root = ir_from_source(source)
    source_bytes = source.encode("utf-8")
    index = LineIndex(source, source_bytes)
    ids: list[str] = []
    for node in walk_ir(root):
        ids.append(node.id)
        assert source_bytes[node.span.start_byte : node.span.end_byte].decode("utf-8") == (
            node.source_text
        )
        start_line, start_column, end_line, end_column = index.span(
            node.span.start_byte,
            node.span.end_byte,
        )
        assert (node.span.start_line, node.span.start_column) == (start_line, start_column)
        assert (node.span.end_line, node.span.end_column) == (end_line, end_column)
        assert node.editable is False
    assert len(ids) == len(set(ids))


def test_cyrillic_identifier_uses_utf16_columns() -> None:
    source = read_java_fixture("cyrillic.java")
    root = ir_from_source(source)
    method = find_method_by_name(root, "метод")
    assert method is not None
    body = method.role_child("body")
    assert body is not None
    returned = body.children[0]
    identifier = returned.role_child("value")
    assert identifier is not None
    assert identifier.name == "значение"
    assert identifier.span.start_line == 3
    assert identifier.span.start_column == 12
    assert identifier.span.end_column == 20


def test_comments_keep_text_and_class_header_is_not_unsupported() -> None:
    source = read_java_fixture("comments.java")
    root = ir_from_source(source)
    comments = [node for node in walk_ir(root) if node.kind == IrNodeKind.COMMENT]
    texts = {node.source_text for node in comments}
    assert "// заметка" in texts
    assert "/* блок */" in texts

    header = """
package demo;
import java.util.List;
class Box<T> extends Base implements Marker {
  void m() { return; }
}
"""
    boxed = ir_from_source(header)
    classes = [node for node in walk_ir(boxed) if node.kind == IrNodeKind.CLASS]
    assert classes[0].name == "Box"
    assert classes[0].superclass_text == "extends Base"
    assert classes[0].interfaces_text == "implements Marker"
    assert classes[0].type_parameters_text == "<T>"
    assert find_method_by_name(boxed, "m") is not None
    assert not any(node.kind == IrNodeKind.UNSUPPORTED for node in walk_ir(boxed))


def test_switch_is_modeled_in_ir() -> None:
    source = read_java_fixture("unsupported_switch.java")
    root = ir_from_source(source)
    unsupported = [node for node in walk_ir(root) if node.kind == IrNodeKind.UNSUPPORTED]
    assert unsupported == []
    switches = [node for node in walk_ir(root) if node.kind == IrNodeKind.SWITCH]
    assert len(switches) == 1
    assert "switch" in switches[0].source_text
    assert list_methods(root)[0].name == "m"


def test_try_keeps_catch_and_finally_in_ir() -> None:
    source = read_java_fixture("try_statement.java")
    root = ir_from_source(source)
    method = find_method_by_name(root, "m")
    assert method is not None
    body = method.role_child("body")
    assert body is not None
    try_node = body.children[0]
    assert try_node.kind == IrNodeKind.TRY
    nested = [child.kind for child in try_node.children]
    assert IrNodeKind.CATCH in nested
    assert IrNodeKind.FINALLY in nested
    catch = next(child for child in try_node.children if child.kind == IrNodeKind.CATCH)
    parameter = catch.role_child("parameters")
    assert parameter is not None
    assert parameter.name == "error"
