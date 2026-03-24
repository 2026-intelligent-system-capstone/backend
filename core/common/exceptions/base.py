class CustomException(Exception):
    code = 400
    error_code = "BAD_GATEWAY"
    message = "BAD GATEWAY"
    detail = None

    def __init__(
            self,
            code: int | None = None,
            message: str | None = None,
            *,
            detail: dict | str | None = None
    ):
        if code:
            self.code = code
        if message:
            self.message = message
        if detail:
            self.detail = detail


class ValueObjectEnumException(CustomException):
    code = 400
    error_code = "ENUM__INVALID"
    message = "유효하지 않은 Enum 값입니다."


class ResourceNotFoundException(CustomException):
    code = 404
    error_code = "RESOURCE_NOT_FOUND"
    message = "요청한 리소스를 찾을 수 없습니다."
