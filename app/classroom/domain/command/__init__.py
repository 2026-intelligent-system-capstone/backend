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
