from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.classroom.domain.entity import ClassroomMaterialSourceKind


class CreateClassroomCommand(BaseModel):
    organization_id: UUID
    name: str
    professor_ids: list[UUID]
    grade: int
    semester: str
    section: str
    description: str | None = None
    student_ids: list[UUID] = Field(default_factory=list)
    allow_student_material_access: bool = False


class InviteClassroomStudentsCommand(BaseModel):
    student_ids: list[UUID] = Field(default_factory=list)


class UpdateClassroomCommand(BaseModel):
    name: str | None = None
    professor_ids: list[UUID] | None = None
    grade: int | None = None
    semester: str | None = None
    section: str | None = None
    description: str | None = None
    student_ids: list[UUID] | None = None
    allow_student_material_access: bool | None = None


class RemoveClassroomStudentCommand(BaseModel):
    student_id: UUID


class CreateClassroomMaterialCommand(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    week: int = Field(..., ge=1, le=16)
    description: str | None = Field(None, max_length=1000)
    source_kind: ClassroomMaterialSourceKind
    source_url: str | None = Field(None, max_length=2000)

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


class UpdateClassroomMaterialCommand(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    week: int | None = Field(None, ge=1, le=16)
    description: str | None = Field(None, max_length=1000)
    source_kind: ClassroomMaterialSourceKind | None = None
    source_url: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def validate_source(self):
        if self.source_kind is ClassroomMaterialSourceKind.LINK:
            if self.source_url is None:
                raise ValueError("링크 자료에는 source_url이 필요합니다.")
        if self.source_kind is ClassroomMaterialSourceKind.FILE:
            if self.source_url is not None:
                raise ValueError(
                    "파일 자료에는 source_url을 함께 보낼 수 없습니다."
                )
        if self.source_kind is None and self.source_url is not None:
            raise ValueError(
                "source_url 수정 시 source_kind를 함께 지정해야 합니다."
            )
        return self
