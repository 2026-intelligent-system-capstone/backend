from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    # App
    ENV: str = "dev"
    ALGORITHM: str = "HS256"

    # JWT
    ACCESS_TOKEN_SECRET_KEY: str = "very-secret-key-change-it-in-prod"
    REFRESH_TOKEN_SECRET_KEY: str = "very-secret-key-change-it-in-prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080

    # RDBMS
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/postgres"

    # In-Memory Database
    VALKEY_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


config = Config()
