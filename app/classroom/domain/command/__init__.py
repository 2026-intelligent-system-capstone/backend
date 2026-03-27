from uuid import UUID

from pydantic import BaseModel, Field


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


class UpdateClassroomMaterialCommand(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    week: int | None = Field(None, ge=1, le=16)
    description: str | None = Field(None, max_length=1000)
