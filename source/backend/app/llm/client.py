"""HTTP-клиент LLM: DeepSeek (Bearer) и совместимые провайдеры; GigaChat OAuth - legacy."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.llm.credentials import LlmCredentials

logger = logging.getLogger("app.llm")


class LlmClientError(Exception):
    """Ошибка вызова LLM без утечки ключа и полного ответа провайдера клиенту."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class _CachedToken:
    access_token: str
    expires_at_ms: float


_token_lock = threading.Lock()
_token_cache: dict[str, _CachedToken] = {}
_TOKEN_SKEW_MS = 60_000


def chat_completion(
    *,
    credentials: LlmCredentials,
    base_url: str,
    oauth_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    verify_ssl: bool = True,
    http_referer: str | None = None,
    app_title: str | None = None,
) -> str:
    """Возвращает текст content первого choice. Ключ в логи не пишется."""
    del http_referer, app_title
    if credentials.provider in {"deepseek", "openai_compatible", "openrouter_legacy"}:
        effective_base = credentials.base_url or base_url
        return _bearer_completion(
            api_key=credentials.authorization_key,
            base_url=effective_base,
            payload=payload,
            timeout_seconds=timeout_seconds,
            verify_ssl=verify_ssl,
        )

    access_token = _get_access_token(
        credentials=credentials,
        oauth_url=oauth_url,
        timeout_seconds=timeout_seconds,
        verify_ssl=verify_ssl,
    )
    return _bearer_completion(
        api_key=access_token,
        base_url=base_url,
        payload=payload,
        timeout_seconds=timeout_seconds,
        verify_ssl=verify_ssl,
    )


def _bearer_completion(
    *,
    api_key: str,
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    verify_ssl: bool,
) -> str:
    root = base_url.rstrip("/")
    url = root if root.endswith("/chat/completions") else root + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    last_error: Exception | None = None
    response: httpx.Response | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=timeout_seconds, verify=verify_ssl) as client:
                response = client.post(url, headers=headers, json=payload)
            if response.status_code == 429 and attempt == 0:
                logger.warning("llm_http_status status=429 attempt=1; backoff")
                time.sleep(2.5)
                continue
            break
        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning(
                "llm_timeout timeout_seconds=%s attempt=%s",
                timeout_seconds,
                attempt + 1,
            )
            if attempt == 0:
                time.sleep(1.5)
                continue
            raise LlmClientError("timeout") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning(
                "llm_transport_error type=%s timeout_seconds=%s attempt=%s",
                type(exc).__name__,
                timeout_seconds,
                attempt + 1,
            )
            if attempt == 0:
                time.sleep(2.0)
                continue
            raise LlmClientError("transport") from exc
    if response is None:
        raise LlmClientError("transport") from last_error

    if response.status_code >= 400:
        logger.warning("llm_http_status status=%s", response.status_code)
        raise LlmClientError(f"http_{response.status_code}")

    try:
        body = response.json()
    except ValueError as exc:
        raise LlmClientError("invalid_json") from exc
    return _extract_content(body)


def _get_access_token(
    *,
    credentials: LlmCredentials,
    oauth_url: str,
    timeout_seconds: float,
    verify_ssl: bool,
) -> str:
    cache_key = f"{credentials.authorization_key[:16]}:{credentials.scope}:{oauth_url}"
    now_ms = time.time() * 1000
    with _token_lock:
        cached = _token_cache.get(cache_key)
        if cached is not None and cached.expires_at_ms - _TOKEN_SKEW_MS > now_ms:
            return cached.access_token

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {credentials.authorization_key}",
    }
    try:
        with httpx.Client(timeout=min(60.0, timeout_seconds), verify=verify_ssl) as client:
            response = client.post(
                oauth_url,
                headers=headers,
                data={"scope": credentials.scope},
            )
    except httpx.TimeoutException as exc:
        logger.warning("llm_oauth_timeout")
        raise LlmClientError("timeout") from exc
    except httpx.HTTPError as exc:
        logger.warning("llm_oauth_transport_error")
        raise LlmClientError("transport") from exc

    if response.status_code >= 400:
        reason = _oauth_failure_reason(response.status_code, response.text)
        logger.warning("llm_oauth_http_status status=%s reason=%s", response.status_code, reason)
        raise LlmClientError(reason)

    try:
        body = response.json()
    except ValueError as exc:
        raise LlmClientError("invalid_json") from exc

    token = body.get("access_token")
    expires_at = body.get("expires_at")
    if not isinstance(token, str) or not token.strip():
        raise LlmClientError("oauth_empty_token")
    if isinstance(expires_at, (int, float)):
        expires_at_ms = float(expires_at)
        if expires_at_ms < 10_000_000_000:
            expires_at_ms *= 1000
    else:
        expires_at_ms = time.time() * 1000 + 25 * 60 * 1000

    with _token_lock:
        _token_cache[cache_key] = _CachedToken(access_token=token, expires_at_ms=expires_at_ms)
    return token


def _extract_content(body: Any) -> str:
    if not isinstance(body, dict):
        raise LlmClientError("invalid_json")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LlmClientError("empty_choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise LlmClientError("missing_message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LlmClientError("empty_content")
    return content


def clear_token_cache() -> None:
    """Сброс кэша токенов (для тестов)."""
    with _token_lock:
        _token_cache.clear()


def _oauth_failure_reason(status_code: int, body_text: str) -> str:
    lowered = body_text.lower()
    if "credentials doesn't match db data" in lowered or '"code":6' in lowered.replace(" ", ""):
        return "oauth_credentials_mismatch"
    if "can't decode" in lowered or '"code":4' in lowered.replace(" ", ""):
        return "oauth_authorization_header_invalid"
    if "scope" in lowered and ("code\":7" in lowered.replace(" ", "") or "code\":6" in lowered):
        return "oauth_scope_mismatch"
    return f"http_{status_code}"
