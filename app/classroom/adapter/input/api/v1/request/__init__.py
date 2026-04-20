from uuid import UUID

from pydantic import AnyHttpUrl, Field, model_validator

from app.classroom.domain.entity import ClassroomMaterialSourceKind
from core.common.request.base import BaseRequest


class CreateClassroomRequest(BaseRequest):
    name: str = Field(..., min_length=2, max_length=100)
    professor_ids: list[UUID] = Field(..., min_length=1)
    grade: int = Field(..., ge=1, le=6)
    semester: str = Field(..., min_length=1, max_length=20)
    section: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(None, max_length=500)
    student_ids: list[UUID] = Field(default_factory=list)
    allow_student_material_access: bool = Field(False)


class InviteClassroomStudentsRequest(BaseRequest):
    student_ids: list[UUID] = Field(..., min_length=1)


class UpdateClassroomRequest(BaseRequest):
    null_fields = {"description"}

    name: str | None = Field(None, min_length=2, max_length=100)
    professor_ids: list[UUID] | None = Field(None, min_length=1)
    grade: int | None = Field(None, ge=1, le=6)
    semester: str | None = Field(None, min_length=1, max_length=20)
    section: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = Field(None, max_length=500)
    student_ids: list[UUID] | None = Field(None)
    allow_student_material_access: bool | None = Field(None)

    @model_validator(mode="after")
    def validate_non_empty_update(self):
        if not self.model_fields_set:
            raise ValueError("최소 하나 이상의 수정 필드가 필요합니다.")
        return self


class CreateClassroomMaterialRequest(BaseRequest):
    null_fields = {"description", "source_url"}

    title: str = Field(..., min_length=1, max_length=200)
    week: int = Field(..., ge=1, le=16)
    description: str | None = Field(None, max_length=1000)
    source_kind: ClassroomMaterialSourceKind = Field(
        ClassroomMaterialSourceKind.FILE
    )
    source_url: AnyHttpUrl | None = Field(None)

    @model_validator(mode="after")
    def validate_source(self):
        if self.source_kind is ClassroomMaterialSourceKind.LINK:
            if self.source_url is None:
                raise ValueError("링크 자료에는 source_url이 필요합니다.")
        elif self.source_url is not None:
            raise ValueError(
                "파일 자료에는 source_url을 함께 보낼 수 없습니다."
            )
        return self


class UpdateClassroomMaterialRequest(BaseRequest):
    null_fields = {"description", "source_url"}

    title: str | None = Field(None, min_length=1, max_length=200)
    week: int | None = Field(None, ge=1, le=16)
    description: str | None = Field(None, max_length=1000)
    source_kind: ClassroomMaterialSourceKind | None = Field(None)
    source_url: AnyHttpUrl | None = Field(None)

    @model_validator(mode="after")
    def validate_non_empty_material_update(self):
        if not self.model_fields_set:
            raise ValueError("최소 하나 이상의 수정 필드가 필요합니다.")
        if self.source_kind is ClassroomMaterialSourceKind.LINK:
            if self.source_url is None:
                raise ValueError("링크 자료에는 source_url이 필요합니다.")
        if self.source_kind is ClassroomMaterialSourceKind.FILE:
            if self.source_url is not None:
                raise ValueError(
                    "파일 자료에는 source_url을 함께 보낼 수 없습니다."
                )
        if self.source_kind is None and "source_url" in self.model_fields_set:
            raise ValueError(
                "source_url 수정 시 source_kind를 함께 지정해야 합니다."
            )
        return self
