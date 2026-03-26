from core.common.exceptions.base import CustomException


class ExamNotFoundException(CustomException):
    code = 404
    error_code = "EXAM__NOT_FOUND"
    message = "평가를 찾을 수 없습니다."
