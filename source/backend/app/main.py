"""ASGI-точка входа: `uvicorn app.main:app`."""

from __future__ import annotations

from app.application import create_app

app = create_app()
