from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urlparse
from uuid import UUID

from app.classroom.domain.entity import (
    ClassroomMaterialScopeCandidate,
    ClassroomMaterialSourceKind,
)
from app.classroom.domain.exception import (
    ClassroomMaterialIngestDomainException,
)


@dataclass(frozen=True)
class ClassroomMaterialIngestRequest:
    material_id: UUID
    classroom_id: UUID
    title: str
    week: int
    description: str | None
    source_kind: ClassroomMaterialSourceKind
    file_name: str
    mime_type: str
    content: bytes
    source_url: str | None = None


@dataclass(frozen=True)
class ClassroomMaterialExtractedChunk:
    text: str
    source_type: str
    source_unit_type: str
    citation_label: str
    chunk_index: int
    source_locator: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ClassroomMaterialIngestResult:
    scope_candidates: list[ClassroomMaterialScopeCandidate] = field(
        default_factory=list
    )
    extracted_chunks: list[ClassroomMaterialExtractedChunk] = field(
        default_factory=list
    )
    support_status: str = "supported"
    generated_description: str | None = None


def validate_classroom_material_source_url(source_url: str) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"}:
        raise ClassroomMaterialIngestDomainException(
            message="허용되지 않는 링크 주소입니다."
        )

    hostname = parsed.hostname
    if hostname is None:
        raise ClassroomMaterialIngestDomainException(
            message="허용되지 않는 링크 주소입니다."
        )


class ClassroomMaterialIngestPort(ABC):
    @abstractmethod
    async def ingest_material(
        self,
        *,
        request: ClassroomMaterialIngestRequest,
    ) -> ClassroomMaterialIngestResult:
        """Ingest one classroom material and extract scope candidates."""
