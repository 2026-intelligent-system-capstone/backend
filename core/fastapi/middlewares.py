from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from core.config import config
from core.fastapi.authentication import (
    AuthenticationMiddleware,
    CookieAuthBackend,
)


def make_middleware() -> list[Middleware]:
    return [
        Middleware(
            CORSMiddleware,
            allow_origins=config.FRONTEND_CORS_ORIGIN,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(AuthenticationMiddleware, backend=CookieAuthBackend()),
    ]
