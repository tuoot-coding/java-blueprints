from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import BACKEND_ROOT, Settings

CONFIG_ENV_NAMES = (
    "DEBUG",
    "API_HOST",
    "API_PORT",
    "CORS_ALLOWED_ORIGINS",
    "DATABASE_URL",
    "STORAGE_DIR",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def clear_config_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in CONFIG_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def load_settings() -> Settings:
    return Settings(_env_file=None)


def test_defaults_are_safe() -> None:
    settings = load_settings()

    assert settings.debug is False
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.cors_allowed_origins == ("http://localhost:3000",)
    assert settings.effective_log_level == "INFO"


def test_cors_origins_are_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000, http://127.0.0.1:3000/ ,https://demo.test"
    )

    settings = load_settings()

    assert settings.cors_allowed_origins == (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://demo.test",
    )


@pytest.mark.parametrize(
    "origin",
    ["*", "localhost:3000", "ftp://localhost", "http://localhost:3000/app", "http://u:p@host"],
)
def test_invalid_cors_origin_is_rejected(monkeypatch: pytest.MonkeyPatch, origin: str) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origin)

    with pytest.raises(ValidationError):
        load_settings()


@pytest.mark.parametrize(
    ("debug", "log_level", "expected_level"),
    [
        ("false", "", "INFO"),
        ("true", "", "DEBUG"),
        ("true", "warning", "WARNING"),
        ("false", "DEBUG", "DEBUG"),
    ],
)
def test_effective_log_level_follows_debug_unless_explicit(
    monkeypatch: pytest.MonkeyPatch, debug: str, log_level: str, expected_level: str
) -> None:
    monkeypatch.setenv("DEBUG", debug)
    monkeypatch.setenv("LOG_LEVEL", log_level)

    assert load_settings().effective_log_level == expected_level


def test_unknown_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "VERBOSE")

    with pytest.raises(ValidationError):
        load_settings()


@pytest.mark.parametrize("port", ["0", "65536", "http"])
def test_invalid_port_is_rejected(monkeypatch: pytest.MonkeyPatch, port: str) -> None:
    monkeypatch.setenv("API_PORT", port)

    with pytest.raises(ValidationError):
        load_settings()


@pytest.mark.parametrize("url", ["postgresql://db/app", "sqlite:///", "sqlite://memory"])
def test_non_sqlite_file_database_url_is_rejected(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", url)

    with pytest.raises(ValidationError):
        load_settings()


def test_relative_paths_are_resolved_from_backend_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_DIR", "./var/custom-storage")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./var/custom.sqlite3")

    settings = load_settings()

    assert settings.storage_dir == (BACKEND_ROOT / "var" / "custom-storage").resolve()
    assert settings.database_path == (BACKEND_ROOT / "var" / "custom.sqlite3").resolve()


def test_absolute_storage_dir_is_kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    assert load_settings().storage_dir == tmp_path
