from fastapi.middleware import Middleware

from core.fastapi.authentication import (
    AuthenticationMiddleware,
    CookieAuthBackend,
)


def make_middleware() -> list[Middleware]:
    return [Middleware(AuthenticationMiddleware, backend=CookieAuthBackend())]
