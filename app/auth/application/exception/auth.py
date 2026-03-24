from core.common.exceptions.base import CustomException


class AuthInvalidCredentialsException(CustomException):
    code = 401
    error_code = "AUTH__INVALID_CREDENTIALS"
    message = "학교 계정 정보가 올바르지 않습니다."


class AuthInvalidRefreshTokenException(CustomException):
    code = 401
    error_code = "AUTH__INVALID_REFRESH_TOKEN"
    message = "리프레시 토큰이 유효하지 않습니다."


class AuthUnauthorizedException(CustomException):
    code = 401
    error_code = "AUTH__UNAUTHORIZED"
    message = "인증이 필요합니다."


class AuthIdentityProviderNotConfiguredException(CustomException):
    code = 503
    error_code = "AUTH__IDENTITY_PROVIDER_NOT_CONFIGURED"
    message = "학교 인증 연동이 아직 구성되지 않았습니다."


class AuthIdentityProviderUnavailableException(CustomException):
    code = 503
    error_code = "AUTH__IDENTITY_PROVIDER_UNAVAILABLE"
    message = "학교 인증 시스템에 연결할 수 없습니다."
