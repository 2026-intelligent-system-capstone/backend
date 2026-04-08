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


class ExamQuestionGenerationMaterialNotFoundException(CustomException):
    code = 400
    error_code = "EXAM_QUESTION_GENERATION__INVALID_SOURCE_MATERIALS"
    message = "선택한 강의 자료를 찾을 수 없습니다."


class ExamQuestionGenerationMaterialNotReadyException(CustomException):
    code = 400
    error_code = "EXAM_QUESTION_GENERATION__SOURCE_MATERIALS_NOT_READY"
    message = (
        "선택한 강의 자료에 아직 처리 중인 항목이 있습니다. "
        "적재가 완료된 뒤 다시 시도해주세요."
    )


class ExamQuestionGenerationMaterialIngestFailedException(CustomException):
    code = 400
    error_code = "EXAM_QUESTION_GENERATION__SOURCE_MATERIALS_INGEST_FAILED"
    message = (
        "선택한 강의 자료 중 적재에 실패한 항목이 있습니다. "
        "자료 상태를 확인한 뒤 다시 시도해주세요."
    )


class ExamQuestionGenerationContextUnavailableException(CustomException):
    code = 422
    error_code = "EXAM_QUESTION_GENERATION__CONTEXT_UNAVAILABLE"
    message = "선택한 범위에서 관련 강의 자료 문맥을 찾지 못했습니다."


class ExamQuestionGenerationFailedException(CustomException):
    code = 502
    error_code = "EXAM_QUESTION_GENERATION__FAILED"
    message = "AI가 유효한 문항을 생성하지 못했습니다. 다시 시도해주세요."


class ExamSessionAlreadyInProgressException(CustomException):
    code = 409
    error_code = "EXAM_SESSION__ALREADY_IN_PROGRESS"
    message = "이미 진행 중인 평가가 있습니다."


class ExamSessionMaxAttemptsExceededException(CustomException):
    code = 409
    error_code = "EXAM_SESSION__MAX_ATTEMPTS_EXCEEDED"
    message = "허용된 평가 진행 횟수를 초과했습니다."
