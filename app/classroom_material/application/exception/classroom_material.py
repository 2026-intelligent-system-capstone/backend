from core.common.exceptions.base import CustomException


class ClassroomMaterialNotFoundException(CustomException):
    code = 404
    error_code = "CLASSROOM_MATERIAL__NOT_FOUND"
    message = "강의 자료를 찾을 수 없습니다."
