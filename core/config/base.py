from typing import Literal

from pydantic_settings import BaseSettings

type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
type LogFormat = Literal["plain", "json", "uvicorn"]
type CookieSameSite = Literal["lax", "strict", "none"]


class CommonSettings(BaseSettings):
    DEBUG: bool = False
    PROFILING_ENABLED: bool = False

    APP_NAME: str = "Dialearn"
    APP_DESCRIPTION: str = (
        "Conversational AI learning competency assessment platform"
    )
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"

    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:password@localhost:5432/postgres"
    )
    VALKEY_URL: str = "redis://localhost:6379/0"

    ACCESS_TOKEN_SECRET_KEY: str = "very-secret-key-change-it-in-prod"
    REFRESH_TOKEN_SECRET_KEY: str = "very-secret-key-change-it-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080
    ACCESS_TOKEN_COOKIE_NAME: str = "access_token"
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: CookieSameSite = "lax"

    HANSUNG_LOGIN_URL: str = (
        "https://info.hansung.ac.kr/servlet/s_gong.gong_login_ssl"
    )
    HANSUNG_INFO_URL: str = (
        "https://info.hansung.ac.kr/jsp/sugang/h_sugang_sincheong_main.jsp"
    )
    HANSUNG_REQUEST_TIMEOUT_SECONDS: float = 10.0

    SQLALCHEMY_ECHO: bool = False
    FRONTEND_CORS_ORIGIN: list[str] = []

    OPENAPI_URL: str | None = "/api/openapi.json"
    DOCS_URL: str | None = "/api/docs"
    REDOC_URL: str | None = "/api/redoc"

    LOG_LEVEL: LogLevel = "INFO"
    LOG_FORMAT: LogFormat = "plain"
    LOG_DEBUG: bool = False
