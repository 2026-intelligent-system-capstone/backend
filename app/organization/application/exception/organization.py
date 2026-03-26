from core.common.exceptions.base import CustomException


class OrganizationNotFoundException(CustomException):
    code = 404
    error_code = "ORGANIZATION__NOT_FOUND"
    message = "조직을 찾을 수 없습니다."


class OrganizationCodeAlreadyExistsException(CustomException):
    code = 409
    error_code = "ORGANIZATION__CODE_ALREADY_EXISTS"
    message = "이미 사용 중인 조직 코드입니다."
