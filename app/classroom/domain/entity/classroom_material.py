from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from core.common.entity import Entity


@dataclass
class ClassroomMaterial(Entity):
    classroom_id: UUID
    file_id: UUID
    title: str
    week: int
    description: str | None
    uploaded_by: UUID
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        classroom_id: UUID,
        file_id: UUID,
        title: str,
        week: int,
        description: str | None,
        uploaded_by: UUID,
    ) -> "ClassroomMaterial":
        return cls(
            classroom_id=classroom_id,
            file_id=file_id,
            title=title,
            week=week,
            description=description,
            uploaded_by=uploaded_by,
        )

    def belongs_to(self, classroom_id: UUID) -> bool:
        return self.classroom_id == classroom_id

    def update(
        self,
        *,
        title: str | None = None,
        week: int | None = None,
        description: str | None = None,
        replace_description: bool = False,
    ) -> None:
        if title is not None:
            self.title = title
        if week is not None:
            self.week = week
        if replace_description:
            self.description = description

    def replace_file(self, file_id: UUID) -> UUID:
        old_file_id = self.file_id
        self.file_id = file_id
        return old_file_id
