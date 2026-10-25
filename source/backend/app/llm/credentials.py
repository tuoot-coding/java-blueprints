"""Загрузка учетных данных LLM из переменной окружения или файла `api`."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import BACKEND_ROOT

_PROVIDER_RE = re.compile(r"(?i)^\s*Provider\s+(\S+)\s*$")
_API_KEY_RE = re.compile(r"(?i)^\s*API\s+Key\s+(\S+)\s*$")
_BASE_URL_RE = re.compile(r"(?i)^\s*Base\s+URL\s+(\S+)\s*$")
_MODEL_RE = re.compile(r"(?i)^\s*Model\s+(\S+)\s*$")
_AUTH_KEY_LINE_RE = re.compile(
    r"(?i)^\s*Authorization\s+Key\s+([A-Za-z0-9+/=]+)\s*$"
)
_CLIENT_ID_LINE_RE = re.compile(
    r"(?i)^\s*Client\s+ID\s+([0-9a-fA-F-]{8,})\s*$"
)
_SCOPE_LINE_RE = re.compile(
    r"(?i)^\s*Scope\s+(GIGACHAT_API_(?:PERS|B2B|CORP))\s*$"
)
_OPENROUTER_BEARER_RE = re.compile(
    r"Authorization:\s*Bearer\s+(sk-or-v1-[A-Za-z0-9]+)",
    re.IGNORECASE,
)
_OPENROUTER_PLAIN_RE = re.compile(r"^sk-or-v1-[A-Za-z0-9]+$")
_DEEPSEEK_KEY_RE = re.compile(r"^sk-[A-Za-z0-9]{16,}$")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/=]{20,}$")

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"


@dataclass(frozen=True, slots=True)
class LlmCredentials:
    """Ключ LLM и параметры провайдера (DeepSeek / GigaChat / legacy)."""

    authorization_key: str
    scope: str = "GIGACHAT_API_PERS"
    client_id: str | None = None
    provider: str = "deepseek"
    base_url: str | None = None
    model: str | None = None


def repository_root() -> Path:
    return BACKEND_ROOT.parent


def default_api_key_file() -> Path:
    return repository_root() / "api"


def extract_deepseek_credentials(raw: str) -> LlmCredentials | None:
    """Разбирает файл api в формате Provider / API Key / Base URL / Model."""
    provider: str | None = None
    api_key: str | None = None
    base_url = DEFAULT_DEEPSEEK_BASE_URL
    model = DEFAULT_DEEPSEEK_MODEL
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _PROVIDER_RE.match(stripped)
        if match is not None:
            provider = match.group(1).lower()
            continue
        match = _API_KEY_RE.match(stripped)
        if match is not None:
            api_key = match.group(1)
            continue
        match = _BASE_URL_RE.match(stripped)
        if match is not None:
            base_url = match.group(1).rstrip("/")
            continue
        match = _MODEL_RE.match(stripped)
        if match is not None:
            model = match.group(1)
            continue
        if api_key is None and _DEEPSEEK_KEY_RE.fullmatch(stripped):
            api_key = stripped
            provider = provider or "deepseek"

    if api_key is None:
        return None
    if api_key.startswith("sk-REPLACE") or "ваш_" in api_key.lower():
        return None
    if provider is None:
        provider = "deepseek" if api_key.startswith("sk-") and not api_key.startswith("sk-or-") else None
    if provider not in {"deepseek", "openai_compatible"}:
        if provider is None and _DEEPSEEK_KEY_RE.fullmatch(api_key):
            provider = "deepseek"
        else:
            return None
    return LlmCredentials(
        authorization_key=api_key,
        provider=provider,
        base_url=base_url,
        model=model,
    )


def extract_gigachat_credentials(raw: str) -> LlmCredentials | None:
    """Разбирает устаревший формат Authorization Key / Client ID / Scope."""
    auth_key: str | None = None
    client_id: str | None = None
    scope = "GIGACHAT_API_PERS"
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _AUTH_KEY_LINE_RE.match(stripped)
        if match is not None:
            auth_key = match.group(1)
            continue
        match = _CLIENT_ID_LINE_RE.match(stripped)
        if match is not None:
            client_id = match.group(1)
            continue
        match = _SCOPE_LINE_RE.match(stripped)
        if match is not None:
            scope = match.group(1).upper()
            continue
        if auth_key is None and _BASE64_RE.fullmatch(stripped) and ":" not in stripped[:8]:
            if "=" in stripped or len(stripped) >= 40:
                auth_key = stripped

    if auth_key is None:
        return None
    return LlmCredentials(
        authorization_key=auth_key,
        scope=scope,
        client_id=client_id,
        provider="gigachat",
    )


def extract_api_key_from_text(raw: str) -> str | None:
    """Возвращает ключ DeepSeek / GigaChat / OpenRouter из произвольного текста."""
    deep = extract_deepseek_credentials(raw)
    if deep is not None:
        return deep.authorization_key
    creds = extract_gigachat_credentials(raw)
    if creds is not None:
        return creds.authorization_key
    match = _OPENROUTER_BEARER_RE.search(raw)
    if match is not None:
        return match.group(1)
    for line in raw.splitlines():
        stripped = line.strip().strip('"').strip("'")
        if _DEEPSEEK_KEY_RE.fullmatch(stripped) or _OPENROUTER_PLAIN_RE.fullmatch(stripped):
            return stripped
    return None


def load_llm_credentials(
    *,
    env_key: str | None,
    key_file: Path | None,
    default_scope: str = "GIGACHAT_API_PERS",
) -> LlmCredentials | None:
    """Приоритет: LLM_API_KEY, затем файл api. DeepSeek предпочтителен."""
    if env_key is not None:
        cleaned = env_key.strip()
        if cleaned:
            if cleaned.startswith("sk-or-v1-"):
                return LlmCredentials(
                    authorization_key=cleaned,
                    scope=default_scope,
                    provider="openrouter_legacy",
                )
            if _DEEPSEEK_KEY_RE.fullmatch(cleaned):
                return LlmCredentials(
                    authorization_key=cleaned,
                    provider="deepseek",
                    base_url=DEFAULT_DEEPSEEK_BASE_URL,
                    model=DEFAULT_DEEPSEEK_MODEL,
                )
            return LlmCredentials(
                authorization_key=cleaned,
                scope=default_scope,
                provider="gigachat",
            )
    path = key_file if key_file is not None else default_api_key_file()
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    deep = extract_deepseek_credentials(text)
    if deep is not None:
        return deep
    creds = extract_gigachat_credentials(text)
    if creds is not None:
        return creds
    legacy = extract_api_key_from_text(text)
    if legacy is None:
        return None
    if _DEEPSEEK_KEY_RE.fullmatch(legacy):
        return LlmCredentials(
            authorization_key=legacy,
            provider="deepseek",
            base_url=DEFAULT_DEEPSEEK_BASE_URL,
            model=DEFAULT_DEEPSEEK_MODEL,
        )
    return LlmCredentials(
        authorization_key=legacy,
        scope=default_scope,
        provider="openrouter_legacy" if legacy.startswith("sk-or-v1-") else "gigachat",
    )


def load_llm_api_key(
    *,
    env_key: str | None,
    key_file: Path | None,
) -> str | None:
    """Совместимость: возвращает строку API key / Authorization Key."""
    creds = load_llm_credentials(env_key=env_key, key_file=key_file)
    return None if creds is None else creds.authorization_key
