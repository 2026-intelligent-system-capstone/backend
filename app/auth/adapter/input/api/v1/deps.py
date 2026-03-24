from uuid import UUID

import jwt
from dependency_injector.wiring import Provide, inject
from fastapi import Cookie, Depends

from app.auth.application.exception import AuthUnauthorizedException
from app.auth.container import AuthContainer
from app.auth.domain.entity import CurrentUser
from app.user.domain.entity import UserStatus
from app.user.domain.repository import UserRepository
from core.config import config
from core.domain.types import TokenType
from core.helpers.token import TokenHelper


@inject
async def require_authenticated_user(
    access_token: str | None = Cookie(
        default=None,
        alias=config.ACCESS_TOKEN_COOKIE_NAME,
    ),
    user_repository: UserRepository = Depends(
        Provide[AuthContainer.user_repository]
    ),
) -> CurrentUser:
    if access_token is None:
        raise AuthUnauthorizedException()

    try:
        payload = TokenHelper.decode_token(access_token)
        if payload.get("type") != TokenType.ACCESS.value:
            raise AuthUnauthorizedException()
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise AuthUnauthorizedException() from exc

    user = await user_repository.get_by_id(user_id)
    if user is None or user.status == UserStatus.BLOCKED:
        raise AuthUnauthorizedException()

    return CurrentUser.from_user(user)
