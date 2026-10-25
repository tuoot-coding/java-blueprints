from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth_gate import CSRF_HEADER
from app.auth.models import AuthTokenPurpose
from app.auth.tokens import hash_opaque_token
from tests.conftest import TEST_USER_EMAIL, TEST_USER_PASSWORD, login_client, seed_verified_user


def test_health_remains_public(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/api/v1/health")
    assert response.status_code == 200


def test_protected_route_requires_auth(anonymous_client: TestClient) -> None:
    response = anonymous_client.post(
        "/api/v1/parser/parse",
        json={"source": "class A {}", "file_name": "A.java"},
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "auth_required"


def test_register_login_me_logout_flow(application: FastAPI, anonymous_client: TestClient) -> None:
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "AnotherSafePass1"  # noqa: S105

    register = anonymous_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": f"u{uuid4().hex[:8]}",
            "password": password,
            "role": "user",
        },
    )
    assert register.status_code == 202

    # Без подтверждения вход запрещён.
    denied = anonymous_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert denied.status_code == 403
    assert denied.json()["error_code"] == "auth_email_not_verified"

    store = application.state.auth_store
    user = store.get_user_by_email_normalized(email)
    assert user is not None
    raw = f"tok-{uuid4().hex}"
    now = datetime.now(UTC)
    store.create_auth_token(
        token_id=uuid4().hex,
        user_id=user.id,
        purpose=AuthTokenPurpose.EMAIL_VERIFY,
        token_hash=hash_opaque_token(raw),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    verify = anonymous_client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert verify.status_code == 200

    login_client(anonymous_client, email=email, password=password)
    me = anonymous_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == email

    logout = anonymous_client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    me_after = anonymous_client.get("/api/v1/auth/me")
    assert me_after.status_code == 401


def test_login_invalid_credentials_are_generic(anonymous_client: TestClient) -> None:
    missing = anonymous_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "WrongPassword12"},
    )
    assert missing.status_code == 401
    assert missing.json()["error_code"] == "auth_invalid_credentials"
    message = missing.json()["message"].lower()
    assert "неверный" in message or "email" in message


def test_register_does_not_reveal_existing_account(
    application: FastAPI, anonymous_client: TestClient
) -> None:
    seed_verified_user(
        application,
        email="taken@example.com",
        password=TEST_USER_PASSWORD,
        username="takenuser",
    )
    first = anonymous_client.post(
        "/api/v1/auth/register",
        json={
            "email": "taken@example.com",
            "username": "othername1",
            "password": "BrandNewPassword9",
            "role": "user",
        },
    )
    second = anonymous_client.post(
        "/api/v1/auth/register",
        json={
            "email": "fresh@example.com",
            "username": "freshname1",
            "password": "BrandNewPassword9",
            "role": "admin",
        },
    )
    assert first.status_code == second.status_code == 202
    assert first.json()["message"] == second.json()["message"]


def test_password_reset_flow(application: FastAPI, anonymous_client: TestClient) -> None:
    email = f"reset-{uuid4().hex[:8]}@example.com"
    seed_verified_user(application, email=email, password=TEST_USER_PASSWORD)

    asked = anonymous_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
    )
    assert asked.status_code == 202

    store = application.state.auth_store
    user = store.get_user_by_email_normalized(email)
    assert user is not None
    raw = f"reset-{uuid4().hex}"
    now = datetime.now(UTC)
    store.create_auth_token(
        token_id=uuid4().hex,
        user_id=user.id,
        purpose=AuthTokenPurpose.PASSWORD_RESET,
        token_hash=hash_opaque_token(raw),
        created_at=now,
        expires_at=now + timedelta(minutes=30),
    )

    new_password = "ResetPasswordSafe1"  # noqa: S105
    confirmed = anonymous_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw, "new_password": new_password},
    )
    assert confirmed.status_code == 200

    old_login = anonymous_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_USER_PASSWORD},
    )
    assert old_login.status_code == 401

    login_client(anonymous_client, email=email, password=new_password)
    assert anonymous_client.get("/api/v1/auth/me").status_code == 200


def test_csrf_required_for_logout(application: FastAPI, anonymous_client: TestClient) -> None:
    seed_verified_user(application, email=TEST_USER_EMAIL, password=TEST_USER_PASSWORD)
    login = anonymous_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )
    assert login.status_code == 200
    # Cookie есть, заголовка CSRF нет.
    anonymous_client.headers.pop(CSRF_HEADER, None)
    denied = anonymous_client.post("/api/v1/auth/logout")
    assert denied.status_code == 403
    assert denied.json()["error_code"] == "auth_csrf_failed"


def test_authenticated_client_can_parse(client: TestClient) -> None:
    response = client.post("/api/v1/parser/parse", json={"source": "class Demo {}"})
    assert response.status_code == 200
