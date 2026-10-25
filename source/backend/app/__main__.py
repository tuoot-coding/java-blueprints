"""Запуск сервера с API_HOST и API_PORT из конфигурации: `python -m app`."""

from __future__ import annotations

import uvicorn

from app.core.config import get_settings


def run_server() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
        access_log=False,
        server_header=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    run_server()
