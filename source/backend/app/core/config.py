"""Типизированная конфигурация Backend из переменных окружения и backend/.env."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
AuthStoreKind = Literal["mysql", "memory"]
CookieSameSite = Literal["strict", "lax", "none"]

SQLITE_URL_PREFIX = "sqlite:///"


class Settings(BaseSettings):
    """Параметры запуска.

    Значения по умолчанию безопасны для локальной разработки: сервер слушает только
    loopback, DEBUG выключен, CORS разрешен только для локального Frontend.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    debug: bool = False
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_allowed_origins: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:3000",)
    database_url: str = f"{SQLITE_URL_PREFIX}./var/java_blueprints.sqlite3"
    storage_dir: Path = Path("./var/storage")
    # Достаточно для файлов >1000 строк (по умолчанию 4 МиБ UTF-8).
    max_java_source_bytes: int = Field(default=4_194_304, ge=1, le=16_777_216)
    # LLM через DeepSeek (файл api в корне) или LLM_API_KEY.
    llm_enabled: bool = True
    llm_api_key: str | None = None
    llm_api_key_file: Path | None = None
    llm_base_url: str = "https://api.deepseek.com"
    llm_oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    llm_model: str = "deepseek-chat"
    llm_scope: str = "GIGACHAT_API_PERS"
    llm_verify_ssl: bool = True
    llm_timeout_seconds: float = Field(default=180.0, ge=1.0, le=600.0)
    llm_include_flowchart_assist: bool = False
    # --- Изолированный запуск Java (Docker JDK 21) ---
    java_docker_image: str = "eclipse-temurin:21-jdk"
    # Жёсткие лимиты, чтобы эфемерные контейнеры не раздували RAM/CPU хоста.
    java_docker_memory: str = "384m"
    java_docker_cpus: str = "1.0"
    java_docker_pids_limit: int = Field(default=64, ge=8, le=256)
    # TTL контейнера на весь набор тестов (максимум 5 минут).
    java_suite_timeout_seconds: float = Field(default=300.0, ge=15.0, le=300.0)
    # Лимит одного stdin-кейса внутри контейнера.
    java_case_timeout_seconds: float = Field(default=30.0, ge=1.0, le=60.0)
    # Compose: каталог внутри Backend, куда смонтирован общий volume для JDK-контейнеров.
    java_work_dir: Path | None = None
    # Compose: имя Docker volume (не bind-path) - иначе daemon не видит /tmp контейнера Backend.
    java_docker_work_volume: str | None = None
    log_level: LogLevel | None = None
    # Подробный лог действий в отдельный файл (ротация).
    log_file: Path = Path("./var/logs/java_blueprints.log")
    log_to_file: bool = True

    # --- Auth (пользователи в MySQL; проекты остаются в SQLite) ---
    # По умолчанию memory - тесты и openapi без MySQL. В compose: AUTH_STORE=mysql.
    auth_store: AuthStoreKind = "memory"
    auth_mysql_dsn: str | None = None
    # ВРЕМЕННО для разработки: API без обязательного входа (LLM / схема->код / parse).
    auth_api_gate_enabled: bool = False
    # ВРЕМЕННО для разработки: без письма подтверждения и без жёсткой политики пароля.
    auth_dev_auto_verify_email: bool = True
    auth_session_ttl_seconds: int = Field(default=86_400, ge=300, le=2_592_000)
    auth_cookie_name: str = "jb_session"
    auth_csrf_cookie_name: str = "jb_csrf"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: CookieSameSite = "strict"
    auth_password_min_length: int = Field(default=1, ge=1, le=128)
    auth_enforce_password_complexity: bool = False
    auth_hibp_enabled: bool = False
    auth_hibp_timeout_seconds: float = Field(default=3.0, ge=0.5, le=30.0)
    auth_email_verify_ttl_seconds: int = Field(default=86_400, ge=300, le=604_800)
    auth_password_reset_ttl_seconds: int = Field(default=3_600, ge=300, le=86_400)
    auth_login_rate_max: int = Field(default=5, ge=1, le=100)
    auth_login_rate_window_seconds: int = Field(default=300, ge=30, le=86_400)
    auth_reset_rate_max: int = Field(default=3, ge=1, le=100)
    auth_reset_rate_window_seconds: int = Field(default=300, ge=30, le=86_400)
    public_app_base_url: str = "http://localhost:3000"
    smtp_host: str = "127.0.0.1"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@java-blueprints.local"
    smtp_use_tls: bool = False

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, raw_value: object) -> object:
        """Принимает список origin через запятую, как он записывается в .env."""
        if isinstance(raw_value, str):
            return tuple(item.strip() for item in raw_value.split(",") if item.strip())
        return raw_value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        """Origin должен быть точным scheme://host[:port] без пути; маска "*" запрещена."""
        for origin in origins:
            parts = urlsplit(origin)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or parts.path not in {"", "/"}
                or parts.query
                or parts.fragment
                or parts.username
                or parts.password
            ):
                raise ValueError(f"недопустимый origin в CORS_ALLOWED_ORIGINS: {origin!r}")
        return tuple(origin.rstrip("/") for origin in origins)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, url: str) -> str:
        """На текущем этапе поддерживается только локальный SQLite-файл."""
        if not url.startswith(SQLITE_URL_PREFIX) or url == SQLITE_URL_PREFIX:
            raise ValueError("DATABASE_URL должен иметь вид sqlite:///<путь к файлу>")
        return url

    @field_validator("storage_dir")
    @classmethod
    def resolve_storage_dir(cls, path: Path) -> Path:
        """Относительный путь отсчитывается от каталога backend/, а не от текущей директории."""
        return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()

    @field_validator("log_file")
    @classmethod
    def resolve_log_file(cls, path: Path) -> Path:
        return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()

    @field_validator("llm_api_key_file", mode="before")
    @classmethod
    def empty_llm_key_file(cls, raw_value: object) -> object:
        if isinstance(raw_value, str) and not raw_value.strip():
            return None
        return raw_value

    @field_validator("llm_api_key_file")
    @classmethod
    def resolve_llm_api_key_file(cls, path: Path | None) -> Path | None:
        if path is None:
            return None
        return path if path.is_absolute() else (BACKEND_ROOT.parent / path).resolve()

    @field_validator("llm_api_key", mode="before")
    @classmethod
    def empty_llm_api_key(cls, raw_value: object) -> object:
        if isinstance(raw_value, str) and not raw_value.strip():
            return None
        return raw_value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, raw_value: object) -> object:
        """Пустой LOG_LEVEL означает уровень, производный от DEBUG."""
        if isinstance(raw_value, str):
            stripped = raw_value.strip().upper()
            return stripped or None
        return raw_value

    @field_validator(
        "auth_mysql_dsn",
        "smtp_username",
        "smtp_password",
        "java_docker_work_volume",
        mode="before",
    )
    @classmethod
    def empty_optional_str(cls, raw_value: object) -> object:
        if isinstance(raw_value, str) and not raw_value.strip():
            return None
        return raw_value

    @field_validator("java_work_dir", mode="before")
    @classmethod
    def empty_java_work_dir(cls, raw_value: object) -> object:
        if isinstance(raw_value, str) and not raw_value.strip():
            return None
        return raw_value

    @field_validator("java_work_dir")
    @classmethod
    def resolve_java_work_dir(cls, path: Path | None) -> Path | None:
        if path is None:
            return None
        return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()

    @field_validator("java_docker_work_volume")
    @classmethod
    def validate_java_docker_work_volume(cls, name: str | None) -> str | None:
        if name is None:
            return None
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name):
            raise ValueError("JAVA_DOCKER_WORK_VOLUME: недопустимое имя volume")
        return name

    @field_validator("public_app_base_url")
    @classmethod
    def validate_public_app_base_url(cls, url: str) -> str:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("PUBLIC_APP_BASE_URL должен быть абсолютным URL")
        return url.rstrip("/")

    @model_validator(mode="after")
    def validate_auth_store(self) -> Settings:
        if self.auth_store == "mysql" and not self.auth_mysql_dsn:
            raise ValueError(
                "AUTH_MYSQL_DSN обязателен при AUTH_STORE=mysql "
                "(для тестов используйте AUTH_STORE=memory)"
            )
        if self.auth_mysql_dsn and not (
            self.auth_mysql_dsn.startswith("mysql://")
            or self.auth_mysql_dsn.startswith("mysql+pymysql://")
        ):
            raise ValueError("AUTH_MYSQL_DSN должен начинаться с mysql:// или mysql+pymysql://")
        return self

    @property
    def database_path(self) -> Path:
        """Файл SQLite; относительный путь отсчитывается от каталога backend/."""
        path = Path(self.database_url.removeprefix(SQLITE_URL_PREFIX))
        return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()

    @property
    def effective_log_level(self) -> LogLevel:
        """Явный LOG_LEVEL имеет приоритет, иначе DEBUG переключает DEBUG/INFO."""
        if self.log_level is not None:
            return self.log_level
        return "DEBUG" if self.debug else "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Единственный экземпляр настроек процесса."""
    return Settings()
