from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.request_context import REQUEST_ID_HEADER
from tests.conftest import TEST_FRONTEND_ORIGIN

HEALTH_PATH = "/api/v1/health"


def test_allowed_origin_receives_cors_headers(client: TestClient) -> None:
    response = client.get(HEALTH_PATH, headers={"Origin": TEST_FRONTEND_ORIGIN})

    assert response.headers["access-control-allow-origin"] == TEST_FRONTEND_ORIGIN
    assert REQUEST_ID_HEADER.lower() in response.headers["access-control-expose-headers"].lower()


def test_allowed_origin_preflight_succeeds(client: TestClient) -> None:
    response = client.options(
        HEALTH_PATH,
        headers={"Origin": TEST_FRONTEND_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == TEST_FRONTEND_ORIGIN


def test_unknown_origin_is_not_allowed(client: TestClient) -> None:
    response = client.get(HEALTH_PATH, headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_headers_present_on_error_responses(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist", headers={"Origin": TEST_FRONTEND_ORIGIN})

    assert response.status_code == 404
    assert response.headers["access-control-allow-origin"] == TEST_FRONTEND_ORIGIN
