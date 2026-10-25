"""Настройка логирования и контекст запроса для структурированных записей."""

from __future__ import annotations

import logging
import logging.config
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from app.core.config import LogLevel

NO_REQUEST_ID = "-"

request_id_context: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST_ID)

_activity_logger = logging.getLogger("app.activity")


class RequestContextFilter(logging.Filter):
    """Добавляет request_id текущего HTTP-запроса в каждую запись лога."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


def configure_logging(level: LogLevel, *, log_file: Path | None = None) -> None:
    """Единый формат key=value для приложения и uvicorn.

    Access-лог uvicorn отключается: запросы логирует middleware приложения вместе
    с request_id и длительностью. При указании log_file пишется отдельный файл
    с ротацией. Полный исходный код пользователя в лог не пишется.
    """
    handlers: dict[str, Any] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "filters": ["request_context"],
        },
    }
    root_handlers = ["console"]

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "structured",
            "filters": ["request_context"],
            "filename": str(log_file),
            "maxBytes": 5_000_000,
            "backupCount": 5,
            "encoding": "utf-8",
        }
        root_handlers.append("file")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"request_context": {"()": RequestContextFilter}},
            "formatters": {
                "structured": {
                    "format": (
                        "%(asctime)s level=%(levelname)s logger=%(name)s "
                        "request_id=%(request_id)s %(message)s"
                    ),
                },
            },
            "handlers": handlers,
            "root": {"level": level, "handlers": root_handlers},
            "loggers": {
                "uvicorn": {"level": level, "handlers": [], "propagate": True},
                "uvicorn.error": {"level": level, "handlers": [], "propagate": True},
                "uvicorn.access": {"level": "WARNING", "handlers": [], "propagate": False},
                "app.activity": {"level": "DEBUG", "handlers": [], "propagate": True},
            },
        }
    )
    if log_file is not None:
        logging.getLogger("app").info("file_logging_enabled path=%s", log_file)


def log_activity(event: str, **fields: Any) -> None:
    """Подробная запись шага пайплайна без утечки полного исходника."""
    parts = [f"event={event}"]
    for key, value in fields.items():
        if value is None:
            continue
        text = str(value).replace("\n", "\\n")
        if len(text) > 400:
            text = text[:400] + "..."
        parts.append(f"{key}={text}")
    _activity_logger.info(" ".join(parts))
