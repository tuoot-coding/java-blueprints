"""Инварианты CFG перед выдачей клиенту.

Проверяется форма графа, а не эквивалентность Java-программы.
Недостижимый из входа узел допустим: это недостижимый код, а не битое ребро.
"""

from __future__ import annotations

from app.graph.models import CfgGraph, CfgNodeKind, EdgeKind


def validate_cfg_invariants(graph: CfgGraph) -> tuple[str, ...]:
    """Возвращает список нарушений. Пустой кортеж означает, что форма графа принята."""
    if graph.entry_id is None and graph.exit_id is None and not graph.nodes and not graph.edges:
        return ()

    problems: list[str] = []
    node_ids = [node.id for node in graph.nodes]
    if len(node_ids) != len(set(node_ids)):
        problems.append("duplicate_node_id")
    known = set(node_ids)
    if graph.entry_id not in known:
        problems.append("missing_entry")
    if graph.exit_id not in known:
        problems.append("missing_exit")

    edge_ids = [edge.id for edge in graph.edges]
    if len(edge_ids) != len(set(edge_ids)):
        problems.append("duplicate_edge_id")

    kinds = {node.id: node.kind for node in graph.nodes}
    for edge in graph.edges:
        if edge.source_id not in known or edge.target_id not in known:
            problems.append("dangling_edge")
            continue
        if edge.source_id == graph.exit_id:
            problems.append("edge_from_exit")
        if edge.target_id == graph.entry_id:
            problems.append("edge_to_entry")
        if edge.kind in {EdgeKind.TRUE, EdgeKind.FALSE} and (
            kinds.get(edge.source_id) != CfgNodeKind.CONDITION
        ):
            problems.append("branch_edge_from_non_condition")
        if edge.kind == EdgeKind.RETURN and edge.target_id != graph.exit_id:
            problems.append("return_edge_not_to_exit")
    if any(edge.target_id == graph.entry_id for edge in graph.edges):
        problems.append("entry_has_incoming")
    return tuple(dict.fromkeys(problems))
