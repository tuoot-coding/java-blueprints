"""Параметры вызова LLM из Settings и файла api."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.llm.credentials import LlmCredentials, default_api_key_file, load_llm_credentials


@dataclass(frozen=True, slots=True)
class LlmCallOptions:
    credentials: LlmCredentials
    base_url: str
    oauth_url: str
    model: str
    timeout_seconds: float
    verify_ssl: bool


def resolve_llm_options(settings: Settings) -> LlmCallOptions | None:
    credentials = load_llm_credentials(
        env_key=settings.llm_api_key,
        key_file=settings.llm_api_key_file or default_api_key_file(),
        default_scope=settings.llm_scope,
    )
    if not settings.llm_enabled or credentials is None:
        return None
    base_url = credentials.base_url or settings.llm_base_url
    model = credentials.model or settings.llm_model
    return LlmCallOptions(
        credentials=credentials,
        base_url=base_url,
        oauth_url=settings.llm_oauth_url,
        model=model,
        timeout_seconds=settings.llm_timeout_seconds,
        verify_ssl=settings.llm_verify_ssl,
    )
