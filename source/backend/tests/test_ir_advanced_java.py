"""Покрытие IR: record/enum, generics, lambda, Stream, concurrent, reflect, nio, net, time."""

from __future__ import annotations

from app.ir.models import IrNodeKind
from app.ir.query import count_unsupported, find_method_by_name, list_methods, walk_ir
from app.structure.scratch import build_scratch_program
from tests.java_fixtures import ir_from_source, read_java_fixture


def test_advanced_fixture_has_no_unsupported() -> None:
    root = ir_from_source(read_java_fixture("tz_advanced_java.java"))
    assert count_unsupported(root) == 0


def test_record_and_enum_modeled() -> None:
    root = ir_from_source(read_java_fixture("tz_advanced_java.java"))
    kinds = {node.kind for node in walk_ir(root)}
    assert IrNodeKind.ENUM in kinds
    assert IrNodeKind.ENUM_CONSTANT in kinds
    assert IrNodeKind.RECORD in kinds
    assert IrNodeKind.COMPACT_CONSTRUCTOR in kinds
    constants = [
        node.name for node in walk_ir(root) if node.kind == IrNodeKind.ENUM_CONSTANT
    ]
    assert "RED" in constants and "GREEN" in constants
    record = next(node for node in walk_ir(root) if node.kind == IrNodeKind.RECORD)
    assert record.name == "Point"
    params = [child.name for child in record.role_children("parameters")]
    assert params == ["x", "y"]


def test_generics_keep_type_parameters_text() -> None:
    root = ir_from_source(read_java_fixture("tz_advanced_java.java"))
    advanced = next(
        node for node in walk_ir(root) if node.kind == IrNodeKind.CLASS and node.name == "AdvancedTz"
    )
    assert advanced.type_parameters_text is not None
    assert "T" in advanced.type_parameters_text
    identity = find_method_by_name(root, "identity")
    assert identity is not None


def test_lambda_method_reference_and_functional_api() -> None:
    root = ir_from_source(read_java_fixture("tz_advanced_java.java"))
    kinds = {node.kind for node in walk_ir(root)}
    assert IrNodeKind.LAMBDA in kinds
    assert IrNodeKind.METHOD_REFERENCE in kinds
    streams = find_method_by_name(root, "streams")
    assert streams is not None
    body_text = streams.role_child("body").source_text if streams.role_child("body") else ""
    assert "Collectors" in body_text or "stream" in body_text


def test_stream_concurrent_reflect_nio_net_time_via_api_calls() -> None:
    root = ir_from_source(read_java_fixture("tz_advanced_java.java"))
    invocations = " ".join(
        (node.name or "") + " " + node.source_text
        for node in walk_ir(root)
        if node.kind == IrNodeKind.METHOD_INVOCATION
    )
    assert "stream" in invocations or "collect" in invocations or "filter" in invocations
    assert "newFixedThreadPool" in invocations or "submit" in invocations
    assert "getMethod" in invocations or "invoke" in invocations
    assert "writeString" in invocations or "readString" in invocations
    assert "getByName" in invocations or "toURL" in invocations
    assert "now" in invocations or "ofMinutes" in invocations
    assert any(node.kind == IrNodeKind.CLASS_LITERAL for node in walk_ir(root))


def test_advanced_methods_listed_including_compact_ctor() -> None:
    root = ir_from_source(read_java_fixture("tz_advanced_java.java"))
    names = [method.name for method in list_methods(root)]
    assert "Point" in names  # compact constructor
    assert "streams" in names
    assert "concurrent" in names
    assert "reflect" in names
    assert "files" in names
    assert "net" in names
    assert "timeApi" in names


def test_advanced_scratch_has_no_unsupported_blocks() -> None:
    root = ir_from_source(read_java_fixture("tz_advanced_java.java"))
    program = build_scratch_program(root)
    assert len(program.blocks) > 20
    assert not any(block.kind == "unsupported" for block in program.blocks)


def test_anonymous_class_still_unsupported() -> None:
    root = ir_from_source(read_java_fixture("unsupported_anonymous.java"))
    assert count_unsupported(root) >= 1
    assert any(
        node.kind == IrNodeKind.UNSUPPORTED and "class_body" in (node.reason or node.syntax_type)
        or (node.kind == IrNodeKind.UNSUPPORTED)
        for node in walk_ir(root)
    )
