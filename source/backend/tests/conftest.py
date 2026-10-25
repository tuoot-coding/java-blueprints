from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth_gate import CSRF_HEADER
from app.application import create_app
from app.auth.models import AuthTokenPurpose
from app.auth.tokens import hash_opaque_token
from app.core.config import Settings

TEST_FRONTEND_ORIGIN = "http://localhost:3000"
TEST_USER_EMAIL = "tester@example.com"
TEST_USER_USERNAME = "tester"
TEST_USER_PASSWORD = "CorrectHorseBattery1"  # noqa: S105 - тестовый пароль


def build_test_settings(tmp_path: Path, *, debug: bool = False) -> Settings:
    """Настройки без чтения backend/.env, чтобы локальное окружение не влияло на тесты."""
    return Settings(
        _env_file=None,
        debug=debug,
        api_host="127.0.0.1",
        api_port=8000,
        cors_allowed_origins=(TEST_FRONTEND_ORIGIN,),
        database_url=f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}",
        storage_dir=tmp_path / "storage",
        max_java_source_bytes=4_194_304,
        llm_enabled=False,
        llm_api_key=None,
        llm_api_key_file=None,
        llm_base_url="https://api.deepseek.com",
        llm_oauth_url="https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        llm_model="deepseek-chat",
        llm_scope="GIGACHAT_API_PERS",
        llm_verify_ssl=True,
        llm_timeout_seconds=180.0,
        llm_include_flowchart_assist=False,
        log_level=None,
        log_file=tmp_path / "logs" / "test.log",
        log_to_file=False,
        auth_store="memory",
        auth_mysql_dsn=None,
        auth_api_gate_enabled=True,
        auth_dev_auto_verify_email=False,
        auth_hibp_enabled=False,
        auth_cookie_secure=False,
        auth_password_min_length=12,
        auth_enforce_password_complexity=True,
        public_app_base_url="http://localhost:3000",
        smtp_host="127.0.0.1",
        smtp_port=1025,
        smtp_from="noreply@test.local",
        smtp_use_tls=False,
    )


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return build_test_settings(tmp_path)


@pytest.fixture
def application(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


def seed_verified_user(
    app: FastAPI,
    *,
    email: str,
    password: str,
    username: str | None = None,
) -> str:
    """Регистрирует пользователя и сразу подтверждает email. Возвращает raw verify token."""
    from app.auth.models import UserRole

    auth = app.state.auth_service
    store = app.state.auth_store
    resolved_username = username or f"u{uuid4().hex[:10]}"
    auth.register(
        email=email,
        username=resolved_username,
        password=password,
        role=UserRole.USER,
        client_key="seed",
    )
    user = store.get_user_by_email_normalized(email.strip().lower())
    assert user is not None
    raw_token = f"verify-{uuid4().hex}"
    now = datetime.now(UTC)
    store.create_auth_token(
        token_id=uuid4().hex,
        user_id=user.id,
        purpose=AuthTokenPurpose.EMAIL_VERIFY,
        token_hash=hash_opaque_token(raw_token),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    auth.verify_email(token=raw_token)
    return raw_token


def login_client(client: TestClient, *, email: str, password: str) -> str:
    """Логин и CSRF-заголовок по умолчанию для последующих запросов."""
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    csrf = response.json()["csrf_token"]
    client.headers[CSRF_HEADER] = csrf
    return csrf


@pytest.fixture
def anonymous_client(application: FastAPI) -> Iterator[TestClient]:
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def client(application: FastAPI) -> Iterator[TestClient]:
    """Клиент с подтверждённым пользователем и активной сессией (для существующих API-тестов)."""
    seed_verified_user(
        application,
        email=TEST_USER_EMAIL,
        password=TEST_USER_PASSWORD,
        username=TEST_USER_USERNAME,
    )
    with TestClient(application) as test_client:
        login_client(test_client, email=TEST_USER_EMAIL, password=TEST_USER_PASSWORD)
        yield test_client


@pytest.fixture
def auth_helpers(application: FastAPI) -> dict[str, Any]:
    return {
        "app": application,
        "seed": seed_verified_user,
        "login": login_client,
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
    }


@contextmanager
def authed_client(settings: Settings) -> Iterator[TestClient]:
    """TestClient с подтверждённым пользователем (для тестов со своими Settings)."""
    app = create_app(settings)
    seed_verified_user(
        app,
        email=TEST_USER_EMAIL,
        password=TEST_USER_PASSWORD,
        username=TEST_USER_USERNAME,
    )
    with TestClient(app) as client:
        login_client(client, email=TEST_USER_EMAIL, password=TEST_USER_PASSWORD)
        yield client
