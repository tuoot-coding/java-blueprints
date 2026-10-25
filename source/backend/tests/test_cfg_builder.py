from __future__ import annotations

from app.graph.builder import build_method_cfg
from app.graph.models import CfgGraph, CfgNodeKind, EdgeKind
from app.graph.validate import validate_cfg_invariants
from app.ir.models import IrNode
from app.ir.query import find_method_by_name
from tests.java_fixtures import ir_from_source, read_java_fixture


def _method(source: str, name: str) -> IrNode:
    method = find_method_by_name(ir_from_source(source), name)
    assert method is not None
    return method


def _graph(source: str, name: str) -> CfgGraph:
    graph = build_method_cfg(_method(source, name))
    assert validate_cfg_invariants(graph) == ()
    return graph


def _node_id(graph: CfgGraph, snippet: str) -> str:
    matches = [node.id for node in graph.nodes if snippet in node.label]
    assert len(matches) == 1
    return matches[0]


def test_if_else_has_true_false_and_return_edges() -> None:
    graph = _graph(read_java_fixture("control_flow.java"), "branch")
    assert graph.partial is False
    entry = next(node.id for node in graph.nodes if node.kind == CfgNodeKind.ENTRY)
    exit_id = graph.exit_id
    condition = _node_id(graph, "(flag)")
    returned = _node_id(graph, "return;")
    assignment = _node_id(graph, "flag = false;")
    kinds = {(edge.source_id, edge.target_id, edge.kind) for edge in graph.edges}
    assert (entry, condition, EdgeKind.NORMAL) in kinds
    assert (condition, returned, EdgeKind.TRUE) in kinds
    assert (condition, assignment, EdgeKind.FALSE) in kinds
    assert (returned, exit_id, EdgeKind.RETURN) in kinds
    assert (assignment, exit_id, EdgeKind.NORMAL) in kinds
    assert not any(
        edge.source_id == returned and edge.kind == EdgeKind.NORMAL for edge in graph.edges
    )


def test_while_loops_back_to_condition() -> None:
    graph = _graph(read_java_fixture("control_flow.java"), "loop")
    condition = _node_id(graph, "(n > 0)")
    body = _node_id(graph, "n = n - 1;")
    kinds = {(edge.source_id, edge.target_id, edge.kind) for edge in graph.edges}
    assert (condition, body, EdgeKind.TRUE) in kinds
    assert (body, condition, EdgeKind.LOOP_BACK) in kinds
    assert (condition, graph.exit_id, EdgeKind.FALSE) in kinds
    assert graph.partial is False


def test_for_break_and_continue_targets() -> None:
    graph = _graph(read_java_fixture("control_flow.java"), "scan")
    assert graph.partial is False
    condition = _node_id(graph, "i < n")
    update = _node_id(graph, "i++")
    continued = _node_id(graph, "continue;")
    broken = _node_id(graph, "break;")
    kinds = {(edge.source_id, edge.target_id, edge.kind) for edge in graph.edges}
    assert (continued, update, EdgeKind.CONTINUE) in kinds
    assert (update, condition, EdgeKind.LOOP_BACK) in kinds
    assert (broken, graph.exit_id, EdgeKind.BREAK) in kinds
    assert (condition, graph.exit_id, EdgeKind.FALSE) in kinds


def test_try_is_partial_opaque_fallthrough() -> None:
    graph = _graph(read_java_fixture("try_statement.java"), "m")
    assert graph.partial is True
    assert any(item.code == "method_cfg_partial" for item in graph.limitations)
    opaque = [node for node in graph.nodes if node.kind == CfgNodeKind.UNSUPPORTED]
    assert len(opaque) == 1
    assert any(
        edge.source_id == opaque[0].id
        and edge.target_id == graph.exit_id
        and edge.kind == EdgeKind.NORMAL
        for edge in graph.edges
    )
    assert not any(edge.kind in {EdgeKind.TRUE, EdgeKind.FALSE} for edge in graph.edges)


def test_do_and_enhanced_for_are_partial() -> None:
    source = """
class C {
  void m(int n) {
    do {
      n = n - 1;
    } while (n > 0);
    for (int item : values) {
      n = item;
    }
  }
}
"""
    graph = _graph(source, "m")
    assert graph.partial is True
    assert sum(node.kind == CfgNodeKind.UNSUPPORTED for node in graph.nodes) == 2


def test_statement_after_return_is_not_a_successor() -> None:
    graph = _graph(read_java_fixture("unreachable.java"), "m")
    returned = _node_id(graph, "return;")
    dead = _node_id(graph, "int x = 1;")
    assert not any(edge.target_id == dead and edge.source_id == returned for edge in graph.edges)
    assert any(edge.source_id == returned and edge.kind == EdgeKind.RETURN for edge in graph.edges)


def test_validate_cfg_invariants_reports_dangling_edge() -> None:
    from app.graph.models import CfgEdge, CfgNode

    graph = CfgGraph(
        nodes=(
            CfgNode(id="entry", kind=CfgNodeKind.ENTRY, label="вход", ir_node_id=None, span=None),
            CfgNode(id="exit", kind=CfgNodeKind.EXIT, label="выход", ir_node_id=None, span=None),
        ),
        edges=(CfgEdge(id="e1", source_id="entry", target_id="missing", kind=EdgeKind.NORMAL),),
        entry_id="entry",
        exit_id="exit",
        method_name="m",
        method_ir_id="n",
        partial=False,
        limitations=(),
    )
    assert "dangling_edge" in validate_cfg_invariants(graph)
