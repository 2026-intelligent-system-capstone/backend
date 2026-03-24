from core.common.exceptions.base import CustomException


class UserNotFoundException(CustomException):
    code = 404
    error_code = "USER__NOT_FOUND"
    message = "사용자를 찾을 수 없습니다."


class UserAccountAlreadyExistsException(CustomException):
    code = 409
    error_code = "USER__ACCOUNT_ALREADY_EXISTS"
    message = "해당 학교 계정으로 이미 생성된 사용자가 있습니다."


class UserInvalidRoleException(CustomException):
    code = 400
    error_code = "USER__INVALID_ROLE"
    message = "유효하지 않은 사용자 역할입니다."
