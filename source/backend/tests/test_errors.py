from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.request_context import REQUEST_ID_HEADER
from app.application import create_app
from app.core.errors import ApplicationError
from app.schemas.errors import ErrorCode, ErrorResponse
from app.texts.errors import ERROR_MESSAGES
from tests.conftest import build_test_settings

INTERNAL_EXCEPTION_MARKER = "internal-exception-marker"


def _create_app_with_failing_routes(tmp_path: Path, *, debug: bool) -> FastAPI:
    application = create_app(build_test_settings(tmp_path, debug=debug))

    @application.get("/test/unhandled")
    def raise_unhandled() -> None:
        raise RuntimeError(INTERNAL_EXCEPTION_MARKER)

    @application.get("/test/application-error")
    def raise_application_error() -> None:
        raise ApplicationError(ErrorCode.BAD_REQUEST, 409, details={"expected_revision": 3})

    @application.get("/test/validated")
    def read_validated(limit: int) -> dict[str, int]:
        return {"limit": limit}

    return application


def test_every_error_code_has_message() -> None:
    assert set(ERROR_MESSAGES) == set(ErrorCode)


def test_unknown_route_returns_not_found_error(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    error = ErrorResponse.model_validate(response.json())
    assert error.error_code == ErrorCode.NOT_FOUND
    assert error.request_id == response.headers[REQUEST_ID_HEADER]


def test_wrong_method_returns_method_not_allowed(client: TestClient) -> None:
    response = client.post("/api/v1/health")

    assert response.status_code == 405
    assert ErrorResponse.model_validate(response.json()).error_code == ErrorCode.METHOD_NOT_ALLOWED
    assert response.headers["allow"] == "GET"


@pytest.mark.parametrize("debug", [False, True])
def test_unhandled_exception_hides_internals(tmp_path: Path, debug: bool) -> None:
    application = _create_app_with_failing_routes(tmp_path, debug=debug)

    with TestClient(application) as test_client:
        response = test_client.get("/test/unhandled")

    assert response.status_code == 500
    error = ErrorResponse.model_validate(response.json())
    assert error.error_code == ErrorCode.INTERNAL_ERROR
    assert error.request_id == response.headers[REQUEST_ID_HEADER]
    assert INTERNAL_EXCEPTION_MARKER not in response.text
    assert "Traceback" not in response.text


def test_application_error_keeps_status_and_details(tmp_path: Path) -> None:
    application = _create_app_with_failing_routes(tmp_path, debug=False)

    with TestClient(application) as test_client:
        response = test_client.get("/test/application-error")

    assert response.status_code == 409
    error = ErrorResponse.model_validate(response.json())
    assert error.error_code == ErrorCode.BAD_REQUEST
    assert error.details == {"expected_revision": 3}


def test_validation_error_does_not_echo_input(tmp_path: Path) -> None:
    application = _create_app_with_failing_routes(tmp_path, debug=False)
    submitted_value = "class Main { /* user source */ }"

    with TestClient(application) as test_client:
        response = test_client.get("/test/validated", params={"limit": submitted_value})

    assert response.status_code == 422
    error = ErrorResponse.model_validate(response.json())
    assert error.error_code == ErrorCode.VALIDATION_ERROR
    assert error.validation_issues is not None
    assert error.validation_issues[0].location == ["query", "limit"]
    assert submitted_value not in response.text
