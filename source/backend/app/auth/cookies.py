"""Параметры session/CSRF cookies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from starlette.responses import Response

SameSite = Literal["strict", "lax", "none"]


@dataclass(frozen=True, slots=True)
class AuthCookieSettings:
    session_cookie_name: str
    csrf_cookie_name: str
    secure: bool
    samesite: SameSite
    max_age_seconds: int


def set_session_cookies(
    response: Response,
    *,
    settings: AuthCookieSettings,
    session_token: str,
    csrf_token: str,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=settings.max_age_seconds,
        httponly=True,
        secure=settings.secure,
        samesite=settings.samesite,
        path="/",
    )
    # CSRF читается JS и дублируется в заголовке X-CSRF-Token (double-submit).
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=settings.max_age_seconds,
        httponly=False,
        secure=settings.secure,
        samesite=settings.samesite,
        path="/",
    )


def clear_session_cookies(response: Response, *, settings: AuthCookieSettings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.secure,
        httponly=True,
        samesite=settings.samesite,
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        secure=settings.secure,
        httponly=False,
        samesite=settings.samesite,
    )
