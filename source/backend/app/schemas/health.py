"""Ответ GET /api/v1/health."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.services.health import ApplicationHealth


class HealthResponse(BaseModel):
    """Процесс Backend запущен и обрабатывает запросы."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    service: str = Field(description="Имя сервиса.")
    version: str = Field(description="Версия Backend из метаданных пакета.")
    started_at: AwareDatetime = Field(description="Момент запуска процесса, UTC.")
    checked_at: AwareDatetime = Field(description="Момент формирования ответа, UTC.")
    uptime_seconds: float = Field(ge=0, description="Время работы процесса в секундах.")

    @classmethod
    def from_health(cls, health: ApplicationHealth, service: str) -> HealthResponse:
        return cls(
            status="ok",
            service=service,
            version=health.version,
            started_at=health.started_at,
            checked_at=health.checked_at,
            uptime_seconds=health.uptime_seconds,
        )
