"""Оркестрация CFG одного метода."""

from __future__ import annotations

from http import HTTPStatus

from app.core.errors import ApplicationError
from app.graph.builder import build_method_cfg
from app.graph.models import CfgGraph, CfgLimitation
from app.ir.query import list_methods
from app.schemas.errors import ErrorCode
from app.services.inspection import load_java
from app.texts.graph import graph_limitation_message


def build_graph_request(
    source: str,
    *,
    method_name: str | None,
    max_source_bytes: int,
) -> tuple[CfgGraph, str, bool]:
    """Возвращает граф, отпечаток исходника и признак синтаксических ошибок."""
    loaded = load_java(source, max_source_bytes=max_source_bytes)
    methods = list_methods(loaded.ir)
    if method_name is None:
        if not methods:
            empty = _empty_graph("no_method")
            return empty, loaded.source_hash, loaded.inspection.result.has_syntax_errors
        selected = methods[0]
        graph = build_method_cfg(selected)
        if len(methods) > 1:
            graph = _with_limitation(graph, "selected_first_method", None)
        return graph, loaded.source_hash, loaded.inspection.result.has_syntax_errors

    matches = [method for method in methods if method.name == method_name]
    if not matches:
        raise ApplicationError(
            ErrorCode.NOT_FOUND,
            status_code=HTTPStatus.NOT_FOUND,
            details={"method_name": method_name},
        )
    graph = build_method_cfg(matches[0])
    if len(matches) > 1:
        graph = _with_limitation(graph, "ambiguous_method", None)
    return graph, loaded.source_hash, loaded.inspection.result.has_syntax_errors


def _empty_graph(code: str) -> CfgGraph:
    return CfgGraph(
        nodes=(),
        edges=(),
        entry_id=None,
        exit_id=None,
        method_name=None,
        method_ir_id=None,
        partial=False,
        limitations=(
            CfgLimitation(code=code, message=graph_limitation_message(code), syntax_type=None),
        ),
    )


def _with_limitation(graph: CfgGraph, code: str, syntax_type: str | None) -> CfgGraph:
    limitation = CfgLimitation(
        code=code,
        message=graph_limitation_message(code, syntax_type),
        syntax_type=syntax_type,
    )
    if any(item.code == code for item in graph.limitations):
        return graph
    return CfgGraph(
        nodes=graph.nodes,
        edges=graph.edges,
        entry_id=graph.entry_id,
        exit_id=graph.exit_id,
        method_name=graph.method_name,
        method_ir_id=graph.method_ir_id,
        partial=graph.partial,
        limitations=(*graph.limitations, limitation),
    )
