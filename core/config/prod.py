from dataclasses import field

from pydantic_settings import SettingsConfigDict

from .base import CommonSettings, LogFormat


class ProdSettings(CommonSettings):
    DEBUG: bool = False
    PROFILING_ENABLED: bool = False
    FRONTEND_CORS_ORIGIN: list[str] = field(default_factory=lambda: [])
    DOCS_URL: str | None = None
    REDOC_URL: str | None = None
    OPENAPI_URL: str | None = None
    LOG_FORMAT: LogFormat = "json"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.prod"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
