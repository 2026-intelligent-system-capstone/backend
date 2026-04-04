from core.common.exceptions.base import CustomException


class ExamInvalidWeekDomainException(CustomException):
    code = 400
    error_code = "EXAM__INVALID_WEEK"
    message = "유효한 주차 값이 아닙니다."


class ExamQuestionNotFoundDomainException(CustomException):
    code = 404
    error_code = "EXAM_QUESTION__NOT_FOUND"
    message = "문항을 찾을 수 없습니다."


class ExamSessionOwnershipForbiddenDomainException(CustomException):
    code = 403
    error_code = "AUTH__FORBIDDEN"
    message = "접근 권한이 없습니다."


class ExamSessionNotCompletedDomainException(CustomException):
    code = 403
    error_code = "AUTH__FORBIDDEN"
    message = "접근 권한이 없습니다."


class ExamResultNotFoundDomainException(CustomException):
    code = 403
    error_code = "AUTH__FORBIDDEN"
    message = "접근 권한이 없습니다."
