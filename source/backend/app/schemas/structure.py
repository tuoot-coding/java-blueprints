"""Схемы POST /api/v1/structure/build."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.ir.query import IrSummary
from app.schemas.parser import CoordinateSystemSchema
from app.schemas.span import SourceSpanSchema
from app.structure.models import StructuralBlock, StructuralLink


class StructureBuildRequest(BaseModel):
    """Тело запроса структурных блоков."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(description="Исходный текст Java в UTF-8.")


class StructuralLinkSchema(BaseModel):
    """Связь иерархии или последовательности. Это не ребро CFG."""

    model_config = ConfigDict(frozen=True)

    kind: str
    target_id: str


class StructuralBlockSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    parent_id: str | None
    label: str
    ir_node_id: str
    span: SourceSpanSchema
    editable: bool
    supported_operations: list[str]
    links: list[StructuralLinkSchema]

    @classmethod
    def from_block(cls, block: StructuralBlock) -> StructuralBlockSchema:
        return cls(
            id=block.id,
            type=block.type,
            parent_id=block.parent_id,
            label=block.label,
            ir_node_id=block.ir_node_id,
            span=SourceSpanSchema.from_span(block.span),
            editable=block.editable,
            supported_operations=list(block.supported_operations),
            links=[_link_schema(item) for item in block.links],
        )


class IrSummarySchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_count: int = Field(ge=0)
    class_names: list[str]
    method_names: list[str]
    kind_counts: dict[str, int]
    unsupported_count: int = Field(ge=0)

    @classmethod
    def from_summary(cls, summary: IrSummary) -> IrSummarySchema:
        return cls(
            node_count=summary.node_count,
            class_names=list(summary.class_names),
            method_names=list(summary.method_names),
            kind_counts=dict(summary.kind_counts),
            unsupported_count=summary.unsupported_count,
        )


class StructureBuildResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    blocks: list[StructuralBlockSchema]
    ir_summary: IrSummarySchema
    unsupported_count: int = Field(ge=0)
    coordinate_system: CoordinateSystemSchema = (
        CoordinateSystemSchema.LINE_UTF16_COLUMN_1_BASED_HALF_OPEN
    )
    source_hash: str
    has_syntax_errors: bool


def _link_schema(link: StructuralLink) -> StructuralLinkSchema:
    return StructuralLinkSchema(kind=link.kind.value, target_id=link.target_id)
