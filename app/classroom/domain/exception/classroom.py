from core.common.exceptions.base import CustomException


class ClassroomProfessorNotFoundDomainException(CustomException):
    code = 404
    error_code = "CLASSROOM__PROFESSOR_NOT_FOUND"
    message = "강의실 교수자를 찾을 수 없습니다."


class ClassroomStudentNotFoundDomainException(CustomException):
    code = 404
    error_code = "CLASSROOM__STUDENT_NOT_FOUND"
    message = "강의실 학생을 찾을 수 없습니다."


class ClassroomInvalidProfessorRoleDomainException(CustomException):
    code = 400
    error_code = "CLASSROOM__INVALID_PROFESSOR_ROLE"
    message = "교수자 목록에는 교수자만 포함할 수 있습니다."


class ClassroomInvalidStudentRoleDomainException(CustomException):
    code = 400
    error_code = "CLASSROOM__INVALID_STUDENT_ROLE"
    message = "학생 목록에는 학생만 포함할 수 있습니다."


class ClassroomMaterialIngestDomainException(CustomException):
    code = 503
    error_code = "CLASSROOM_MATERIAL__INGEST_FAILED"
    message = "강의 자료 적재 중 오류가 발생했습니다."


class ClassroomMaterialIngestEmptyScopeDomainException(CustomException):
    code = 422
    error_code = "CLASSROOM_MATERIAL__INGEST_EMPTY_SCOPE"
    message = "자료에서 시험 범위 후보를 추출하지 못했습니다."
