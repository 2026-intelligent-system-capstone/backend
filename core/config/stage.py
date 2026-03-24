from pydantic_settings import SettingsConfigDict

from .base import CommonSettings


class StageSettings(CommonSettings):
    ENV: str = "stage"
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.stage"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
