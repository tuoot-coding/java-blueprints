"""Идентификатор HTTP-запроса."""

from __future__ import annotations

import re
import uuid

from fastapi import Request

from app.core.logging import request_id_context

REQUEST_ID_HEADER = "X-Request-ID"
_CLIENT_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def resolve_request_id(client_value: str | None) -> str:
    """Принимает X-Request-ID клиента только в безопасном формате, иначе создает новый."""
    if client_value is not None and _CLIENT_REQUEST_ID_PATTERN.fullmatch(client_value):
        return client_value
    return uuid.uuid4().hex


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else request_id_context.get()
