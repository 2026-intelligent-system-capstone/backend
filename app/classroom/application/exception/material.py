from core.common.exceptions.base import CustomException


class ClassroomMaterialNotFoundException(CustomException):
    code = 404
    error_code = "CLASSROOM_MATERIAL__NOT_FOUND"
    message = "강의 자료를 찾을 수 없습니다."


class ClassroomMaterialInvalidSourceException(CustomException):
    code = 400
    error_code = "CLASSROOM_MATERIAL__INVALID_SOURCE"
    message = "강의 자료 source 설정이 올바르지 않습니다."


class ClassroomMaterialDownloadUnavailableException(CustomException):
    code = 400
    error_code = "CLASSROOM_MATERIAL__DOWNLOAD_UNAVAILABLE"
    message = "링크 자료는 다운로드를 지원하지 않습니다."
