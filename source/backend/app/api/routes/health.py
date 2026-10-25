"""GET /api/v1/health."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_application_runtime
from app.core.metadata import DISTRIBUTION_NAME
from app.schemas.health import HealthResponse
from app.services.health import ApplicationRuntime, get_application_health

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    operation_id="get_health",
    summary="Доступность Backend",
    response_model=HealthResponse,
)
def get_health(
    runtime: Annotated[ApplicationRuntime, Depends(get_application_runtime)],
) -> HealthResponse:
    """Liveness: процесс запущен и отвечает. Внешние зависимости не проверяются."""
    return HealthResponse.from_health(get_application_health(runtime), service=DISTRIBUTION_NAME)
