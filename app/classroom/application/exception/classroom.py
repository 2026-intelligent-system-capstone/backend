from core.common.exceptions.base import CustomException


class ClassroomNotFoundException(CustomException):
    code = 404
    error_code = "CLASSROOM__NOT_FOUND"
    message = "강의실을 찾을 수 없습니다."


class ClassroomAlreadyExistsException(CustomException):
    code = 409
    error_code = "CLASSROOM__ALREADY_EXISTS"
    message = "동일한 강의 정보의 강의실이 이미 존재합니다."


class ClassroomProfessorNotFoundException(CustomException):
    code = 404
    error_code = "CLASSROOM__PROFESSOR_NOT_FOUND"
    message = "강의실 교수자를 찾을 수 없습니다."


class ClassroomStudentNotFoundException(CustomException):
    code = 404
    error_code = "CLASSROOM__STUDENT_NOT_FOUND"
    message = "강의실 학생을 찾을 수 없습니다."


class ClassroomInvalidProfessorRoleException(CustomException):
    code = 400
    error_code = "CLASSROOM__INVALID_PROFESSOR_ROLE"
    message = "교수자 목록에는 교수자만 포함할 수 있습니다."


class ClassroomInvalidStudentRoleException(CustomException):
    code = 400
    error_code = "CLASSROOM__INVALID_STUDENT_ROLE"
    message = "학생 목록에는 학생만 포함할 수 있습니다."


class ClassroomStudentAlreadyInvitedException(CustomException):
    code = 409
    error_code = "CLASSROOM__STUDENT_ALREADY_INVITED"
    message = "이미 강의실에 등록된 학생이 포함되어 있습니다."


class ClassroomStudentNotEnrolledException(CustomException):
    code = 404
    error_code = "CLASSROOM__STUDENT_NOT_ENROLLED"
    message = "강의실에 등록되지 않은 학생입니다."
