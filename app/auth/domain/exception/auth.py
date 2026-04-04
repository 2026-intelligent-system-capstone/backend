from core.common.exceptions.base import CustomException


class AuthInvalidRefreshTokenDomainException(CustomException):
    code = 401
    error_code = "AUTH__INVALID_REFRESH_TOKEN"
    message = "리프레시 토큰이 유효하지 않습니다."
