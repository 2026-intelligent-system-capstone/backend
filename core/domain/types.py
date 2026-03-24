from enum import StrEnum

from core.common.value_object import ValueObject


class TokenType(ValueObject, StrEnum):
    ACCESS = "access_token"
    REFRESH = "refresh_token"
