from core.common.exceptions.base import CustomException


class ExamNotFoundException(CustomException):
    code = 404
    error_code = "EXAM__NOT_FOUND"
    message = "평가를 찾을 수 없습니다."


class ExamQuestionNotFoundException(CustomException):
    code = 404
    error_code = "EXAM_QUESTION__NOT_FOUND"
    message = "문항을 찾을 수 없습니다."


class ExamQuestionGenerationUnavailableException(CustomException):
    code = 503
    error_code = "EXAM_QUESTION_GENERATION__UNAVAILABLE"
    message = "문항 생성 기능을 현재 사용할 수 없습니다."
