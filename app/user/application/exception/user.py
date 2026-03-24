from core.common.exceptions.base import CustomException


class UserNotFoundException(CustomException):
    code = 404
    error_code = "USER__NOT_FOUND"
    message = "사용자를 찾을 수 없습니다."


class UserNameAlreadyExistsException(CustomException):
    code = 409
    error_code = "USER__USERNAME_ALREADY_EXISTS"
    message = "이미 사용 중인 사용자 이름입니다."


class UserEmailAlreadyExistsException(CustomException):
    code = 409
    error_code = "USER__EMAIL_ALREADY_EXISTS"
    message = "이미 사용 중인 이메일입니다."
