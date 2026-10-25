"""Клиент LLM (GigaChat) для логического анализа Java. Не критичен для синтаксического разбора."""

from app.llm.credentials import load_llm_api_key, load_llm_credentials

__all__ = ["load_llm_api_key", "load_llm_credentials"]
