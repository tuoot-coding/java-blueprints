"""Общий диапазон исходника для структурных ответов API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.ir.models import SourceSpan


class SourceSpanSchema(BaseModel):
    """Байты UTF-8 и позиции line/UTF-16 column. Конец диапазона не включается."""

    model_config = ConfigDict(frozen=True)

    start_byte: int = Field(ge=0)
    end_byte: int = Field(ge=0)
    start_line: int = Field(ge=1)
    start_column: int = Field(ge=1)
    end_line: int = Field(ge=1)
    end_column: int = Field(ge=1)

    @classmethod
    def from_span(cls, span: SourceSpan) -> SourceSpanSchema:
        return cls(
            start_byte=span.start_byte,
            end_byte=span.end_byte,
            start_line=span.start_line,
            start_column=span.start_column,
            end_line=span.end_line,
            end_column=span.end_column,
        )
