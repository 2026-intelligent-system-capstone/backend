from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID

from app.classroom.domain.entity import ClassroomMaterialScopeCandidate


@dataclass(frozen=True)
class ClassroomMaterialIngestRequest:
    material_id: UUID
    classroom_id: UUID
    title: str
    week: int
    description: str | None
    file_name: str
    mime_type: str
    content: bytes


@dataclass(frozen=True)
class ClassroomMaterialIngestResult:
    scope_candidates: list[ClassroomMaterialScopeCandidate] = field(
        default_factory=list
    )


class ClassroomMaterialIngestPort(ABC):
    @abstractmethod
    async def ingest_material(
        self,
        *,
        request: ClassroomMaterialIngestRequest,
    ) -> ClassroomMaterialIngestResult:
        """Ingest one classroom material and extract scope candidates."""
