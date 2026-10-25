from __future__ import annotations

import pytest

from app.auth.passwords import hash_password, validate_password_policy, verify_password
from app.core.errors import ApplicationError
from app.schemas.errors import ErrorCode


def test_argon2_hash_and_verify() -> None:
    digest = hash_password("CorrectHorseBattery1")
    assert digest.startswith("$argon2id$")
    assert verify_password(digest, "CorrectHorseBattery1")
    assert not verify_password(digest, "wrong-password")


def test_password_policy_min_length() -> None:
    with pytest.raises(ApplicationError) as exc:
        validate_password_policy("short", min_length=12)
    assert exc.value.error_code == ErrorCode.AUTH_PASSWORD_POLICY


def test_password_policy_rejects_digits_only() -> None:
    with pytest.raises(ApplicationError) as exc:
        validate_password_policy("123456789012", min_length=12, enforce_complexity=True)
    assert exc.value.error_code == ErrorCode.AUTH_PASSWORD_POLICY


def test_password_policy_complexity_can_be_disabled() -> None:
    validate_password_policy("1", min_length=1, enforce_complexity=False)
    validate_password_policy("123456789012", min_length=1, enforce_complexity=False)
