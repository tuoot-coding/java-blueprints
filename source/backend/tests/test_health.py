from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.request_context import REQUEST_ID_HEADER
from app.core.metadata import DISTRIBUTION_NAME, get_application_version
from app.schemas.health import HealthResponse

HEALTH_PATH = "/api/v1/health"


def test_health_returns_valid_liveness_report(client: TestClient) -> None:
    response = client.get(HEALTH_PATH)

    assert response.status_code == 200
    report = HealthResponse.model_validate(response.json())
    assert report.status == "ok"
    assert report.service == DISTRIBUTION_NAME
    assert report.version == get_application_version()
    assert report.uptime_seconds >= 0
    assert report.checked_at >= report.started_at
    assert report.started_at.utcoffset() is not None


def test_health_response_has_exact_contract_fields(client: TestClient) -> None:
    body = client.get(HEALTH_PATH).json()

    assert set(body) == {
        "status",
        "service",
        "version",
        "started_at",
        "checked_at",
        "uptime_seconds",
    }


def test_health_started_at_is_stable_between_requests(client: TestClient) -> None:
    first = HealthResponse.model_validate(client.get(HEALTH_PATH).json())
    second = HealthResponse.model_validate(client.get(HEALTH_PATH).json())

    assert first.started_at == second.started_at
    assert second.uptime_seconds >= first.uptime_seconds


def test_health_generates_request_id(client: TestClient) -> None:
    response = client.get(HEALTH_PATH)

    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id is not None
    assert len(request_id) == 32


def test_health_echoes_safe_client_request_id(client: TestClient) -> None:
    response = client.get(HEALTH_PATH, headers={REQUEST_ID_HEADER: "frontend-req.42"})

    assert response.headers[REQUEST_ID_HEADER] == "frontend-req.42"


def test_health_replaces_unsafe_client_request_id(client: TestClient) -> None:
    unsafe_value = "x" * 65

    response = client.get(HEALTH_PATH, headers={REQUEST_ID_HEADER: unsafe_value})

    assert response.headers[REQUEST_ID_HEADER] != unsafe_value
