"""Схемы POST /api/v1/transform/generate."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GenerateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(description="Исходный текст Java в UTF-8.")


class GenerateResponse(BaseModel):
    """Успешный ответ - тот же исходник, если структурная генерация не отклонена."""

    model_config = ConfigDict(frozen=True)

    source: str
    source_hash: str
    mode: str = Field(
        default="identity_original_source",
        description="Без семантических правок возвращается исходный текст.",
    )
