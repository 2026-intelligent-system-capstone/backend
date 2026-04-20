from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from core.common.entity import Entity


class ClassroomMaterialSourceKind(StrEnum):
    FILE = "file"
    LINK = "link"


class ClassroomMaterialIngestStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ClassroomMaterialOriginalFile:
    file_name: str
    file_path: str
    file_extension: str
    file_size: int
    mime_type: str


@dataclass(frozen=True)
class ClassroomMaterialIngestCapability:
    supported: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "supported": self.supported,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(
        cls, capability: dict[str, object] | None
    ) -> ClassroomMaterialIngestCapability:
        payload = capability or {}
        return cls(
            supported=bool(payload.get("supported", False)),
            reason=(
                str(payload["reason"])
                if payload.get("reason") is not None
                else None
            ),
        )


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
    source_kind: ClassroomMaterialSourceKind
    title: str
    week: int
    description: str | None
    uploaded_by: UUID
    file_id: UUID | None = None
    source_url: str | None = None
    original_file_name: str | None = None
    original_file_path: str | None = None
    original_file_extension: str | None = None
    original_file_size: int | None = None
    original_file_mime_type: str | None = None
    ingest_capability: dict[str, Any] = field(default_factory=dict)
    ingest_metadata: dict[str, Any] = field(default_factory=dict)
    ingest_status: ClassroomMaterialIngestStatus = (
        ClassroomMaterialIngestStatus.PENDING
    )
    scope_candidates: list[dict[str, object]] = field(default_factory=list)
    ingest_error: str | None = None
    created_at: datetime | None = None

    @classmethod
    def create_file(
        cls,
        *,
        classroom_id: UUID,
        file_id: UUID,
        title: str,
        week: int,
        description: str | None,
        uploaded_by: UUID,
        original_file: ClassroomMaterialOriginalFile,
        ingest_capability: ClassroomMaterialIngestCapability,
        ingest_metadata: dict[str, Any] | None = None,
    ) -> ClassroomMaterial:
        return cls(
            classroom_id=classroom_id,
            source_kind=ClassroomMaterialSourceKind.FILE,
            file_id=file_id,
            title=title,
            week=week,
            description=description,
            uploaded_by=uploaded_by,
            source_url=None,
            original_file_name=original_file.file_name,
            original_file_path=original_file.file_path,
            original_file_extension=original_file.file_extension,
            original_file_size=original_file.file_size,
            original_file_mime_type=original_file.mime_type,
            ingest_capability=ingest_capability.to_dict(),
            ingest_metadata=dict(ingest_metadata or {}),
            ingest_status=ClassroomMaterialIngestStatus.PENDING,
            scope_candidates=[],
            ingest_error=None,
        )

    @classmethod
    def create_link(
        cls,
        *,
        classroom_id: UUID,
        source_url: str,
        title: str,
        week: int,
        description: str | None,
        uploaded_by: UUID,
        ingest_capability: ClassroomMaterialIngestCapability,
        ingest_metadata: dict[str, Any] | None = None,
    ) -> ClassroomMaterial:
        return cls(
            classroom_id=classroom_id,
            source_kind=ClassroomMaterialSourceKind.LINK,
            file_id=None,
            title=title,
            week=week,
            description=description,
            uploaded_by=uploaded_by,
            source_url=source_url,
            original_file_name=None,
            original_file_path=None,
            original_file_extension=None,
            original_file_size=None,
            original_file_mime_type=None,
            ingest_capability=ingest_capability.to_dict(),
            ingest_metadata=dict(ingest_metadata or {}),
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
        source_url: str | None = None,
        replace_source_url: bool = False,
        ingest_capability: ClassroomMaterialIngestCapability | None = None,
        replace_ingest_capability: bool = False,
        ingest_metadata: dict[str, Any] | None = None,
        replace_ingest_metadata: bool = False,
    ) -> None:
        if title is not None:
            self.title = title
        if week is not None:
            self.week = week
        if replace_description:
            self.description = description
        if replace_source_url:
            self.source_url = source_url
        if replace_ingest_capability and ingest_capability is not None:
            self.ingest_capability = ingest_capability.to_dict()
        if replace_ingest_metadata:
            self.ingest_metadata = dict(ingest_metadata or {})

    def replace_file(
        self,
        *,
        file_id: UUID,
        original_file: ClassroomMaterialOriginalFile,
        ingest_capability: ClassroomMaterialIngestCapability,
        ingest_metadata: dict[str, Any] | None = None,
    ) -> UUID | None:
        old_file_id = self.file_id
        self.source_kind = ClassroomMaterialSourceKind.FILE
        self.file_id = file_id
        self.source_url = None
        self.original_file_name = original_file.file_name
        self.original_file_path = original_file.file_path
        self.original_file_extension = original_file.file_extension
        self.original_file_size = original_file.file_size
        self.original_file_mime_type = original_file.mime_type
        self.ingest_capability = ingest_capability.to_dict()
        self.ingest_metadata = dict(ingest_metadata or {})
        self.mark_ingest_pending()
        return old_file_id

    def switch_to_link(
        self,
        *,
        source_url: str,
        ingest_capability: ClassroomMaterialIngestCapability,
        ingest_metadata: dict[str, Any] | None = None,
    ) -> UUID | None:
        old_file_id = self.file_id
        self.source_kind = ClassroomMaterialSourceKind.LINK
        self.file_id = None
        self.source_url = source_url
        self.original_file_name = None
        self.original_file_path = None
        self.original_file_extension = None
        self.original_file_size = None
        self.original_file_mime_type = None
        self.ingest_capability = ingest_capability.to_dict()
        self.ingest_metadata = dict(ingest_metadata or {})
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

    def get_original_file(self) -> ClassroomMaterialOriginalFile | None:
        if (
            self.original_file_name is None
            or self.original_file_path is None
            or self.original_file_extension is None
            or self.original_file_size is None
            or self.original_file_mime_type is None
        ):
            return None
        return ClassroomMaterialOriginalFile(
            file_name=self.original_file_name,
            file_path=self.original_file_path,
            file_extension=self.original_file_extension,
            file_size=self.original_file_size,
            mime_type=self.original_file_mime_type,
        )

    def get_ingest_capability(self) -> ClassroomMaterialIngestCapability:
        return ClassroomMaterialIngestCapability.from_dict(
            self.ingest_capability
        )

    def supports_ingest(self) -> bool:
        return self.get_ingest_capability().supported
