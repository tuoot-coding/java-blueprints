"""Криптостойкие opaque-токены и их хеши для хранения."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_opaque_token(*, nbytes: int = 32) -> str:
    """URL-safe случайный токен для cookie или письма."""
    return secrets.token_urlsafe(nbytes)


def hash_opaque_token(token: str) -> str:
    """SHA-256 от токена: в БД хранится только хеш."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
