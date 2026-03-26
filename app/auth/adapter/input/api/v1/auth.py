from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Cookie, Depends, Response

from app.auth.adapter.input.api.v1.request import LoginRequest
from app.auth.container import AuthContainer
from app.auth.domain.command import (
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
)
from app.auth.domain.entity import AuthTokens
from app.auth.domain.usecase.auth import AuthUseCase
from core.config import config

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, tokens: AuthTokens) -> None:
    response.set_cookie(
        key=config.ACCESS_TOKEN_COOKIE_NAME,
        value=tokens.access_token,
        httponly=True,
        secure=config.AUTH_COOKIE_SECURE,
        samesite=config.AUTH_COOKIE_SAMESITE,
        max_age=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key=config.REFRESH_TOKEN_COOKIE_NAME,
        value=tokens.refresh_token,
        httponly=True,
        secure=config.AUTH_COOKIE_SECURE,
        samesite=config.AUTH_COOKIE_SAMESITE,
        max_age=config.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=config.ACCESS_TOKEN_COOKIE_NAME, path="/")
    response.delete_cookie(key=config.REFRESH_TOKEN_COOKIE_NAME, path="/")


@router.post("/login")
@inject
async def login(
    request: LoginRequest,
    response: Response,
    usecase: AuthUseCase = Depends(Provide[AuthContainer.service]),
):
    tokens = await usecase.login(LoginCommand(**request.model_dump()))
    _set_auth_cookies(response, tokens)
    return None


@router.post("/refresh")
@inject
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=config.REFRESH_TOKEN_COOKIE_NAME,
    ),
    usecase: AuthUseCase = Depends(Provide[AuthContainer.service]),
):
    tokens = await usecase.refresh(
        RefreshTokenCommand(refresh_token=refresh_token)
    )
    _set_auth_cookies(response, tokens)
    return None


@router.post("/logout")
@inject
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=config.REFRESH_TOKEN_COOKIE_NAME,
    ),
    usecase: AuthUseCase = Depends(Provide[AuthContainer.service]),
):
    await usecase.logout(LogoutCommand(refresh_token=refresh_token))
    _clear_auth_cookies(response)
    return None
