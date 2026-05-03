from pydantic_settings import SettingsConfigDict

from .base import CommonSettings


class TestSettings(CommonSettings):
    DEBUG: bool = False
    PROFILING_ENABLED: bool = False
    SQLALCHEMY_ECHO: bool = False
    ASYNC_JOB_WORKER_ENABLED: bool = False

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14

    model_config = SettingsConfigDict(
        env_file=(".env.test",),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
