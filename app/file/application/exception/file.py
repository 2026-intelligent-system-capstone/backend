from core.common.exceptions.base import CustomException


class FileNotFoundException(CustomException):
    code = 404
    error_code = "FILE__NOT_FOUND"
    message = "파일을 찾을 수 없습니다."


class FileUploadFailedException(CustomException):
    code = 503
    error_code = "FILE__UPLOAD_FAILED"
    message = "파일 업로드에 실패했습니다."
