from core.common.exceptions.base import CustomException


class ExamInvalidWeekDomainException(CustomException):
    code = 400
    error_code = "EXAM__INVALID_WEEK"
    message = "유효한 주차 값이 아닙니다."


class ExamInvalidMaxAttemptsDomainException(CustomException):
    code = 400
    error_code = "EXAM__INVALID_MAX_ATTEMPTS"
    message = "유효한 총 평가 진행 가능 횟수가 아닙니다."


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


class ExamSessionAlreadyInProgressDomainException(CustomException):
    code = 409
    error_code = "EXAM_SESSION__ALREADY_IN_PROGRESS"
    message = "이미 진행 중인 평가가 있습니다."


class ExamSessionMaxAttemptsExceededDomainException(CustomException):
    code = 409
    error_code = "EXAM_SESSION__MAX_ATTEMPTS_EXCEEDED"
    message = "허용된 평가 진행 횟수를 초과했습니다."
