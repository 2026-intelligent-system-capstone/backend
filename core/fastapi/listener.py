from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

from core.common.exceptions.base import CustomException
from core.fastapi import ExtendedFastAPI


def register_exception_handlers(app: ExtendedFastAPI):
    @app.exception_handler(CustomException)
    async def custom_exception_handler(_: Request, exc: CustomException):
        return JSONResponse(
            status_code=exc.code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=jsonable_encoder(
                {
                    "error_code": "SERVER__REQUEST_VALIDATION_ERROR",
                    "message": "요청값 검증 오류가 발생했습니다.",
                    "detail": exc.errors(),
                }
            ),
        )


def register_handlers(app: ExtendedFastAPI):
    register_exception_handlers(app)
