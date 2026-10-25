"""Состояние доступности процесса Backend."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class ApplicationRuntime:
    """Момент запуска процесса, фиксируется один раз при старте приложения."""

    version: str
    started_at: datetime
    started_monotonic: float

    @classmethod
    def start_now(cls, version: str) -> ApplicationRuntime:
        return cls(
            version=version,
            started_at=datetime.now(UTC),
            started_monotonic=time.monotonic(),
        )


@dataclass(frozen=True, slots=True)
class ApplicationHealth:
    """Liveness-отчет: процесс запущен и обрабатывает HTTP-запросы.

    Внешние зависимости (SQLite, Docker) на этом этапе не подключены и поэтому
    в отчет не входят.
    """

    version: str
    started_at: datetime
    checked_at: datetime
    uptime_seconds: float


def get_application_health(runtime: ApplicationRuntime) -> ApplicationHealth:
    uptime_seconds = max(0.0, time.monotonic() - runtime.started_monotonic)
    return ApplicationHealth(
        version=runtime.version,
        started_at=runtime.started_at,
        checked_at=datetime.now(UTC),
        uptime_seconds=round(uptime_seconds, 3),
    )
