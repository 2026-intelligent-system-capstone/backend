from pydantic_settings import BaseSettings, SettingsConfigDict

class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    ENV: str = "dev"
    SECRET_KEY: str = "very-secret-key-change-it-in-prod"
    ALGORITHM: str = "HS256"
    
    # Token Expiry (minutes)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/postgres"
    VALKEY_URL: str = "redis://localhost:6379/0"

config = Config()
