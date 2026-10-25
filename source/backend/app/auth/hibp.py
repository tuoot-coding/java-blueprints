"""Проверка пароля по Have I Been Pwned (k-anonymity). Fail-open при сбоях сети."""

from __future__ import annotations

import hashlib
import logging

import httpx

logger = logging.getLogger("app.auth.hibp")

HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/{prefix}"


def password_is_pwned(
    password: str,
    *,
    enabled: bool,
    timeout_seconds: float,
    fail_open: bool = True,
) -> bool:
    """True если пароль найден в утечках. При выключенном флаге или ошибке сети - False."""
    if not enabled:
        return False
    digest = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    try:
        response = httpx.get(
            HIBP_RANGE_URL.format(prefix=prefix),
            timeout=timeout_seconds,
            headers={"Add-Padding": "true", "User-Agent": "java-blueprints-auth"},
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("hibp_check_failed fail_open=%s", fail_open)
        return False if fail_open else True

    for line in response.text.splitlines():
        parts = line.split(":")
        if len(parts) >= 1 and parts[0].strip().upper() == suffix:
            return True
    return False
