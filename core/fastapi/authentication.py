from uuid import UUID

import jwt
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    BaseUser,
)
from starlette.middleware.authentication import (
    AuthenticationMiddleware as BaseAuthenticationMiddleware,
)
from starlette.requests import HTTPConnection

from app.auth.domain.entity import RequestUser
from core.config import config
from core.domain.types import TokenType
from core.helpers.token import TokenHelper


class CookieAuthBackend(AuthenticationBackend):
    async def authenticate(
        self,
        conn: HTTPConnection,
    ) -> tuple[AuthCredentials, BaseUser] | None:
        access_token = conn.cookies.get(config.ACCESS_TOKEN_COOKIE_NAME)
        if not access_token:
            return None

        try:
            payload = TokenHelper.decode_token(access_token)
            if payload.get("type") != TokenType.ACCESS.value:
                return None
            user_id = UUID(payload["sub"])
        except jwt.InvalidTokenError:
            return None
        except KeyError:
            return None
        except TypeError:
            return None
        except ValueError:
            return None

        return AuthCredentials(["authenticated"]), RequestUser(id=user_id)


class AuthenticationMiddleware(BaseAuthenticationMiddleware):
    pass
