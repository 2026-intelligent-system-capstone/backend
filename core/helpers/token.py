from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from core.config import config
from core.domain.types import TokenType


class TokenHelper:
    @classmethod
    def create_token(
        cls,
        payload: dict[str, Any],
        token_type: TokenType,
        expires_delta: int | None = None,
    ) -> str:
        """
        Create a JWT token.

        Args:
            payload: Data to include in the token.
            token_type: The type of token (access/refresh).
            expires_delta: Expiration time in minutes. If omitted, use config defaults.
        """
        to_encode = payload.copy()
        expire = datetime.now(UTC) + timedelta(minutes=cls._resolve_expiry_minutes(token_type, expires_delta))

        to_encode.update({"exp": expire, "type": token_type.value})
        return jwt.encode(to_encode, cls._resolve_secret_key(token_type), algorithm=config.ALGORITHM)

    @classmethod
    def decode_token(cls, token: str) -> dict[str, Any]:
        """
        Decode a JWT token.
        """
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        token_type = TokenType.from_value(unverified_payload["type"])
        return jwt.decode(token, cls._resolve_secret_key(token_type), algorithms=[config.ALGORITHM])

    @staticmethod
    def _resolve_secret_key(token_type: TokenType) -> str:
        if token_type == TokenType.ACCESS:
            return config.ACCESS_TOKEN_SECRET_KEY
        if token_type == TokenType.REFRESH:
            return config.REFRESH_TOKEN_SECRET_KEY
        raise ValueError(f"Unsupported token type: {token_type}")

    @staticmethod
    def _resolve_expiry_minutes(token_type: TokenType, expires_delta: int | None) -> int:
        if expires_delta is not None:
            return expires_delta
        if token_type == TokenType.ACCESS:
            return config.ACCESS_TOKEN_EXPIRE_MINUTES
        if token_type == TokenType.REFRESH:
            return config.REFRESH_TOKEN_EXPIRE_MINUTES
        raise ValueError(f"Unsupported token type: {token_type}")
