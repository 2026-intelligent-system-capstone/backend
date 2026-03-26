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
