"""Фабрика FastAPI-приложения."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth_gate import AuthGateMiddleware, CSRF_HEADER
from app.api.error_handlers import register_error_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.request_context import REQUEST_ID_HEADER
from app.api.router import api_router
from app.auth.bootstrap import build_auth_service, build_auth_store
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.metadata import API_TITLE, API_V1_PREFIX, get_application_version
from app.services.health import ApplicationRuntime
from app.storage.sqlite import SqliteProjectStore

logger = logging.getLogger("app")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    SqliteProjectStore(settings.database_path).init_schema()
    app.state.auth_store.init_schema()
    logger.info(
        "application_started version=%s debug=%s log_level=%s cors_origins=%d auth_store=%s",
        app.version,
        settings.debug,
        settings.effective_log_level,
        len(settings.cors_allowed_origins),
        settings.auth_store,
    )
    yield
    logger.info("application_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Фабрика приложения; тесты передают собственные Settings."""
    resolved_settings = settings or get_settings()
    configure_logging(
        resolved_settings.effective_log_level,
        log_file=resolved_settings.log_file if resolved_settings.log_to_file else None,
    )
    version = get_application_version()

    auth_store = build_auth_store(resolved_settings)
    auth_service = build_auth_service(resolved_settings, store=auth_store)

    app = FastAPI(
        title=API_TITLE,
        version=version,
        debug=False,
        openapi_url=f"{API_V1_PREFIX}/openapi.json",
        docs_url=f"{API_V1_PREFIX}/docs",
        redoc_url=f"{API_V1_PREFIX}/redoc",
        lifespan=_lifespan,
    )
    app.state.settings = resolved_settings
    app.state.runtime = ApplicationRuntime.start_now(version)
    app.state.auth_store = auth_store
    app.state.auth_service = auth_service

    register_error_handlers(app)
    # Порядок: последний add_middleware становится внешним слоем.
    # CORS снаружи, затем request context, затем auth gate ближе к приложению.
    app.add_middleware(AuthGateMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", REQUEST_ID_HEADER, CSRF_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.include_router(api_router)
    return app
