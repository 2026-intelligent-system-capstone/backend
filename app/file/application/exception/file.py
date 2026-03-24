from core.common.exceptions.base import CustomException


class FileNotFoundException(CustomException):
    code = 404
    error_code = "FILE__NOT_FOUND"
    message = "파일을 찾을 수 없습니다."
