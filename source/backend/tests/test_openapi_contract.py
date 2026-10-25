from __future__ import annotations

from app.openapi_export import (
    DEFAULT_CONTRACT_PATH,
    build_openapi_document,
    render_openapi_document,
)


def test_committed_contract_matches_application() -> None:
    """contracts/openapi.json обновляется командой `uv run python -m app.openapi_export`."""
    committed = DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8")

    assert committed == render_openapi_document(build_openapi_document())


def test_contract_exposes_only_implemented_endpoints() -> None:
    document = build_openapi_document()

    assert set(document["paths"]) == {
        "/api/v1/health",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/auth/profile",
        "/api/v1/auth/verify-email",
        "/api/v1/auth/resend-verification",
        "/api/v1/auth/password-reset/request",
        "/api/v1/auth/password-reset/confirm",
        "/api/v1/parser/parse",
        "/api/v1/structure/build",
        "/api/v1/graph/build",
        "/api/v1/analysis/analyze",
        "/api/v1/fixes/apply",
        "/api/v1/transform/generate",
        "/api/v1/projects",
        "/api/v1/projects/{project_id}",
        "/api/v1/projects/{project_id}/source",
        "/api/v1/workspace/inspect",
        "/api/v1/workspace/apply-logic-fix",
        "/api/v1/workspace/repair-with-llm",
        "/api/v1/workspace/generate-from-scheme",
    }
    assert set(document["paths"]["/api/v1/health"]) == {"get"}
    assert set(document["paths"]["/api/v1/auth/login"]) == {"post"}
    assert set(document["paths"]["/api/v1/auth/me"]) == {"get"}
    assert set(document["paths"]["/api/v1/auth/change-password"]) == {"post"}
    assert set(document["paths"]["/api/v1/auth/profile"]) == {"patch"}
    assert set(document["paths"]["/api/v1/parser/parse"]) == {"post"}
    assert set(document["paths"]["/api/v1/projects"]) == {"post"}
    assert set(document["paths"]["/api/v1/projects/{project_id}"]) == {"get"}
    assert set(document["paths"]["/api/v1/projects/{project_id}/source"]) == {"put"}


def test_contract_declares_health_parser_and_error_schemas() -> None:
    schemas = build_openapi_document()["components"]["schemas"]

    assert {
        "HealthResponse",
        "ErrorResponse",
        "ErrorCode",
        "ParseJavaRequest",
        "ParseJavaResponse",
        "SyntaxDiagnostic",
        "RegisterRequest",
        "LoginRequest",
        "LoginResponse",
        "AuthUserResponse",
    } <= set(schemas)
    assert "auth_required" in schemas["ErrorCode"]["enum"]
    assert "auth_invalid_credentials" in schemas["ErrorCode"]["enum"]
    health_operation = build_openapi_document()["paths"]["/api/v1/health"]["get"]
    assert health_operation["operationId"] == "get_health"
    assert "500" in health_operation["responses"]
    parse_operation = build_openapi_document()["paths"]["/api/v1/parser/parse"]["post"]
    assert parse_operation["operationId"] == "parse_java_source"
    assert "413" in parse_operation["responses"]
    assert "payload_too_large" in schemas["ErrorCode"]["enum"]
    assert "revision_conflict" in schemas["ErrorCode"]["enum"]
    assert "fix_not_applicable" in schemas["ErrorCode"]["enum"]
    assert "generation_refused" in schemas["ErrorCode"]["enum"]
    assert "llm_unavailable" in schemas["ErrorCode"]["enum"]
    assert "llm_payment_required" in schemas["ErrorCode"]["enum"]
    assert "llm_timeout" in schemas["ErrorCode"]["enum"]
    assert "WorkspaceInspectRequest" in schemas
    assert "GenerateFromSchemeRequest" in schemas
    assert "GenerateFromSchemeResponse" in schemas
    assert "CodeCompareMetricsSchema" in schemas
    assert "SchemeCompareSchema" in schemas
    assert "StructureBuildRequest" in schemas
    assert "GraphBuildResponse" in schemas
    assert "AnalyzeResponse" in schemas
    assert "ApplyFixRequest" in schemas
    assert "GenerateResponse" in schemas
    assert "CreateProjectRequest" in schemas
