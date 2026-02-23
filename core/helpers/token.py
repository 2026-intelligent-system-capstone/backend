from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from core.config import config

class TokenHelper:
    @classmethod
    def _create_token(cls, payload: dict[str, Any], expires_delta: int, is_access: bool = True) -> str:
        to_encode = payload.copy()
        if is_access:
            expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta)
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=expires_delta)
            
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)

    @classmethod
    def create_access_token(cls, payload: dict[str, Any]) -> str:
        return cls._create_token(
            payload=payload, 
            expires_delta=config.ACCESS_TOKEN_EXPIRE_MINUTES,
            is_access=True
        )

    @classmethod
    def create_refresh_token(cls, payload: dict[str, Any]) -> str:
        return cls._create_token(
            payload=payload, 
            expires_delta=config.REFRESH_TOKEN_EXPIRE_DAYS,
            is_access=False
        )

    @classmethod
    def decode_token(cls, token: str) -> dict[str, Any]:
        return jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
