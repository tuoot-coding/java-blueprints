"""Хеширование паролей Argon2id и базовые правила сложности."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.errors import ApplicationError
from app.schemas.errors import ErrorCode

# Параметры OWASP-ориентированные для интерактивного логина.
_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Возвращает Argon2id-хеш со встроенной солью."""
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Проверяет пароль; при устаревших параметрах хеша вызывающий может перехешировать."""
    try:
        return _HASHER.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _HASHER.check_needs_rehash(password_hash)


def validate_password_policy(
    password: str,
    *,
    min_length: int,
    enforce_complexity: bool = True,
) -> None:
    """Проверка пароля: длина всегда; сложность - опционально (выкл. на этапе разработки)."""
    if len(password) < min_length:
        raise ApplicationError(
            ErrorCode.AUTH_PASSWORD_POLICY,
            status_code=422,
            details={"min_length": min_length},
        )
    if not enforce_complexity:
        return
    if password.isascii() and password.isdecimal():
        raise ApplicationError(
            ErrorCode.AUTH_PASSWORD_POLICY,
            status_code=422,
            details={"reason": "digits_only"},
        )
