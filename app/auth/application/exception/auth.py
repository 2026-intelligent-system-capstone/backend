from core.common.exceptions.base import CustomException


class AuthInvalidCredentialsException(CustomException):
    code = 401
    error_code = "AUTH__INVALID_CREDENTIALS"
    message = "이메일 또는 비밀번호가 올바르지 않습니다."


class AuthInvalidRefreshTokenException(CustomException):
    code = 401
    error_code = "AUTH__INVALID_REFRESH_TOKEN"
    message = "리프레시 토큰이 유효하지 않습니다."
