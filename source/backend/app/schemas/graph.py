"""Схемы POST /api/v1/graph/build."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.graph.models import CfgEdge, CfgGraph, CfgLimitation, CfgNode
from app.schemas.parser import CoordinateSystemSchema
from app.schemas.span import SourceSpanSchema


class GraphBuildRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(description="Исходный текст Java в UTF-8.")
    method_name: str | None = Field(default=None, min_length=1, max_length=200)


class CfgNodeSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    label: str
    ir_node_id: str | None
    span: SourceSpanSchema | None


class CfgEdgeSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source_id: str
    target_id: str
    kind: str


class GraphLimitationSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    syntax_type: str | None = None


class GraphBuildResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    method_name: str | None
    method_ir_id: str | None
    nodes: list[CfgNodeSchema]
    edges: list[CfgEdgeSchema]
    entry_id: str | None
    exit_id: str | None
    partial: bool
    limitations: list[GraphLimitationSchema]
    coordinate_system: CoordinateSystemSchema = (
        CoordinateSystemSchema.LINE_UTF16_COLUMN_1_BASED_HALF_OPEN
    )
    source_hash: str
    has_syntax_errors: bool

    @classmethod
    def from_graph(
        cls,
        graph: CfgGraph,
        *,
        source_hash: str,
        has_syntax_errors: bool,
    ) -> GraphBuildResponse:
        return cls(
            method_name=graph.method_name,
            method_ir_id=graph.method_ir_id,
            nodes=[_node_schema(node) for node in graph.nodes],
            edges=[_edge_schema(edge) for edge in graph.edges],
            entry_id=graph.entry_id,
            exit_id=graph.exit_id,
            partial=graph.partial,
            limitations=[_limitation_schema(item) for item in graph.limitations],
            source_hash=source_hash,
            has_syntax_errors=has_syntax_errors,
        )


def _node_schema(node: CfgNode) -> CfgNodeSchema:
    return CfgNodeSchema(
        id=node.id,
        kind=node.kind.value,
        label=node.label,
        ir_node_id=node.ir_node_id,
        span=None if node.span is None else SourceSpanSchema.from_span(node.span),
    )


def _edge_schema(edge: CfgEdge) -> CfgEdgeSchema:
    return CfgEdgeSchema(
        id=edge.id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        kind=edge.kind.value,
    )


def _limitation_schema(item: CfgLimitation) -> GraphLimitationSchema:
    return GraphLimitationSchema(code=item.code, message=item.message, syntax_type=item.syntax_type)
