from pydantic_settings import SettingsConfigDict

from .base import CommonSettings, LogFormat, LogLevel


class DevSettings(CommonSettings):
    DEBUG: bool = True
    PROFILING_ENABLED: bool = True
    SQLALCHEMY_ECHO: bool = True

    LOG_LEVEL: LogLevel = "DEBUG"
    LOG_FORMAT: LogFormat = "uvicorn"
    LOG_DEBUG: bool = True

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.dev"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
