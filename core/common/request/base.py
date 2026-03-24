from collections import namedtuple
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    null_fields: ClassVar[set] = set()
    empty_str_fields: ClassVar[set] = set()

    @model_validator(mode="before")
    @classmethod
    def process_empty_str_or_none(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        return cls._process_dict(data)

    @classmethod
    def _process_dict(cls, data: dict) -> dict:
        res = {}
        for key, value in data.items():
            res[key] = cls._validate_and_transform_value(key, value)
        return res

    @classmethod
    def _validate_and_transform_value(cls, key: str, value: Any) -> Any:
        if isinstance(value, str) and value == "":
            return cls._handle_empty_string(key)
        if value is None:
            return cls._handle_null_value(key)
        return value

    @classmethod
    def _handle_empty_string(cls, key: str) -> str | None:
        if key in cls.empty_str_fields or cls.empty_str_fields == {"*"}:
            return ""
        if key in cls.null_fields or cls.null_fields == {"*"}:
            return None

        raise ValueError(f"필드 '{key}'는 빈 문자열일 수 없습니다.")

    @classmethod
    def _handle_null_value(cls, key: str) -> None:
        if key in cls.null_fields or cls.null_fields == {"*"}:
            return None
        raise ValueError(f"필드 '{key}'는 null일 수 없습니다.")


class PageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(1, description="페이지 번호", ge=1, examples=[1])
    count_by_page: int = Field(12, description="페이지 당 조회 개수", ge=1, le=100, examples=[10])

    def to_prev_limit(self) -> namedtuple("PrevLimit", ["prev", "limit"]):
        return (self.page - 1) * self.count_by_page, self.count_by_page
