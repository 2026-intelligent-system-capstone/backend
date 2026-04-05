from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from core.common.entity import Entity


class ClassroomMaterialIngestStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ClassroomMaterialScopeCandidate:
    label: str
    scope_text: str
    keywords: list[str] = field(default_factory=list)
    week_range: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "scope_text": self.scope_text,
            "keywords": self.keywords,
            "week_range": self.week_range,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(
        cls, candidate: dict[str, object]
    ) -> ClassroomMaterialScopeCandidate:
        return cls(
            label=str(candidate.get("label") or ""),
            scope_text=str(candidate.get("scope_text") or ""),
            keywords=[
                str(keyword)
                for keyword in candidate.get("keywords", [])
                if str(keyword)
            ],
            week_range=(
                str(candidate["week_range"])
                if candidate.get("week_range") is not None
                else None
            ),
            confidence=(
                float(candidate["confidence"])
                if candidate.get("confidence") is not None
                else None
            ),
        )


@dataclass
class ClassroomMaterial(Entity):
    classroom_id: UUID
    file_id: UUID
    title: str
    week: int
    description: str | None
    uploaded_by: UUID
    ingest_status: ClassroomMaterialIngestStatus = (
        ClassroomMaterialIngestStatus.PENDING
    )
    scope_candidates: list[dict[str, object]] = field(default_factory=list)
    ingest_error: str | None = None
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
    ) -> ClassroomMaterial:
        return cls(
            classroom_id=classroom_id,
            file_id=file_id,
            title=title,
            week=week,
            description=description,
            uploaded_by=uploaded_by,
            ingest_status=ClassroomMaterialIngestStatus.PENDING,
            scope_candidates=[],
            ingest_error=None,
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
        self.mark_ingest_pending()
        return old_file_id

    def mark_ingest_pending(self) -> None:
        self.ingest_status = ClassroomMaterialIngestStatus.PENDING
        self.scope_candidates = []
        self.ingest_error = None

    def mark_ingest_completed(
        self,
        scope_candidates: Sequence[ClassroomMaterialScopeCandidate],
    ) -> None:
        self.ingest_status = ClassroomMaterialIngestStatus.COMPLETED
        self.scope_candidates = [
            candidate.to_dict() for candidate in scope_candidates
        ]
        self.ingest_error = None

    def mark_ingest_failed(self, message: str | None = None) -> None:
        self.ingest_status = ClassroomMaterialIngestStatus.FAILED
        self.scope_candidates = []
        self.ingest_error = message

    def get_scope_candidates(self) -> list[ClassroomMaterialScopeCandidate]:
        return [
            ClassroomMaterialScopeCandidate.from_dict(candidate)
            for candidate in self.scope_candidates
        ]
