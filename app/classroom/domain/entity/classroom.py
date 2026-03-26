from dataclasses import dataclass, field
from uuid import UUID

from core.common.entity import Entity


@dataclass
class Classroom(Entity):
    organization_id: UUID
    name: str
    professor_ids: list[UUID] = field(default_factory=list)
    grade: int = 1
    semester: str = "1"
    section: str = "01"
    description: str | None = None
    student_ids: list[UUID] = field(default_factory=list)
    allow_student_material_access: bool = False
