"""Метаданные установленного пакета Backend."""

from __future__ import annotations

from importlib.metadata import version

DISTRIBUTION_NAME = "java-blueprints-backend"
API_TITLE = "Java Blueprints API"
API_V1_PREFIX = "/api/v1"


def get_application_version() -> str:
    """Версия берется из метаданных пакета, то есть из pyproject.toml."""
    return version(DISTRIBUTION_NAME)
