import json
from collections.abc import Iterable
from io import BytesIO
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from openai import AsyncOpenAI
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.classroom.adapter.output.integration.prompts import (
    MATERIAL_SCOPE_CANDIDATES_SYSTEM_PROMPT,
    build_material_scope_candidates_user_prompt,
)
from app.classroom.domain.entity import (
    ClassroomMaterialScopeCandidate,
    ClassroomMaterialSourceKind,
)
from app.classroom.domain.exception import (
    ClassroomMaterialIngestDomainException,
    ClassroomMaterialIngestEmptyScopeDomainException,
)
from app.classroom.domain.service import (
    ClassroomMaterialExtractedChunk,
    ClassroomMaterialIngestPort,
    ClassroomMaterialIngestRequest,
    ClassroomMaterialIngestResult,
)
from core.config import config

TEXT_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/xml",
    "text/xml",
}

OFFICE_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.ms-powerpoint",
    "application/vnd.ms-excel",
}

VIDEO_MIME_PREFIXES = (
    "video/",
    "audio/",
)

YOUTUBE_HOST_MARKERS = (
    "youtube.com",
    "youtu.be",
)

SUPPORTED_STATUS = "supported"
PARTIAL_SUPPORTED_STATUS = "partial_supported"
UNSUPPORTED_STATUS = "unsupported"
MAX_CHUNK_LENGTH = 1000
CHUNK_OVERLAP = 200
MAX_SCOPE_SOURCE_LENGTH = 6000


class LLMClassroomMaterialIngestAdapter(ClassroomMaterialIngestPort):
    async def ingest_material(
        self,
        *,
        request: ClassroomMaterialIngestRequest,
    ) -> ClassroomMaterialIngestResult:
        if not config.OPENAI_API_KEY:
            raise ClassroomMaterialIngestDomainException(
                message="강의 자료 적재 환경이 올바르게 설정되지 않았습니다."
            )

        try:
            extracted_chunks, support_status = self._extract_chunks(request)
        except ClassroomMaterialIngestDomainException:
            raise
        except Exception as exc:
            raise ClassroomMaterialIngestDomainException(
                message="강의 자료를 해석하지 못했습니다."
            ) from exc

        if not extracted_chunks:
            if support_status == UNSUPPORTED_STATUS:
                raise ClassroomMaterialIngestDomainException(
                    message="현재 지원하지 않는 강의 자료 형식입니다."
                )
            raise ClassroomMaterialIngestDomainException(
                message="강의 자료에서 추출된 텍스트가 없습니다."
            )

        try:
            client = QdrantClient(url=config.QDRANT_URL)
            if not client.collection_exists(config.QDRANT_COLLECTION_NAME):
                client.create_collection(
                    collection_name=config.QDRANT_COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=1536,
                        distance=Distance.COSINE,
                    ),
                )

            client.delete(
                collection_name=config.QDRANT_COLLECTION_NAME,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="material_id",
                            match=MatchValue(value=str(request.material_id)),
                        )
                    ]
                ),
            )

            openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            embeddings = await openai_client.embeddings.create(
                model=config.OPENAI_EMBEDDING_MODEL,
                input=[chunk.text for chunk in extracted_chunks],
            )
            client.upsert(
                collection_name=config.QDRANT_COLLECTION_NAME,
                wait=True,
                points=[
                    PointStruct(
                        id=str(uuid4()),
                        vector=embedding.embedding,
                        payload={
                            "classroom_id": str(request.classroom_id),
                            "material_id": str(request.material_id),
                            "title": request.title,
                            "description": request.description,
                            "file_name": request.file_name,
                            "week": request.week,
                            "mime_type": request.mime_type,
                            "support_status": support_status,
                            "source_type": chunk.source_type,
                            "source_unit_type": chunk.source_unit_type,
                            "source_locator": chunk.source_locator,
                            "citation_label": chunk.citation_label,
                            "chunk_index": chunk.chunk_index,
                            "text": chunk.text,
                        },
                    )
                    for chunk, embedding in zip(
                        extracted_chunks,
                        embeddings.data,
                        strict=True,
                    )
                ],
            )

            source_text = "\n".join(
                chunk.text for chunk in extracted_chunks[:5]
            )[:MAX_SCOPE_SOURCE_LENGTH]
            completion = await openai_client.chat.completions.create(
                model=config.OPENAI_EXAM_GENERATION_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": MATERIAL_SCOPE_CANDIDATES_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": build_material_scope_candidates_user_prompt(
                            request=request,
                            source_text=source_text,
                        ),
                    },
                ],
            )
            content = (
                completion.choices[0].message.content or '{"candidates": []}'
            )
            parsed = json.loads(content)
        except ClassroomMaterialIngestDomainException:
            raise
        except Exception as exc:
            raise ClassroomMaterialIngestDomainException(
                message="강의 자료 적재 중 외부 연동 오류가 발생했습니다."
            ) from exc

        if not isinstance(parsed, dict):
            raise ClassroomMaterialIngestDomainException(
                message="강의 자료 범위 후보 응답 형식이 올바르지 않습니다."
            )

        candidates = []
        raw_candidates = parsed.get("candidates", [])
        if not isinstance(raw_candidates, list):
            raise ClassroomMaterialIngestDomainException(
                message="강의 자료 범위 후보 응답 형식이 올바르지 않습니다."
            )

        for item in raw_candidates:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            scope_text = str(item.get("scope_text") or "").strip()
            if not label or not scope_text:
                continue
            raw_keywords = item.get("keywords", [])
            if not isinstance(raw_keywords, list):
                raw_keywords = []
            keywords = [
                str(keyword).strip()
                for keyword in raw_keywords
                if str(keyword).strip()
            ]
            confidence = item.get("confidence")
            candidates.append(
                ClassroomMaterialScopeCandidate(
                    label=label,
                    scope_text=scope_text,
                    keywords=keywords,
                    week_range=(
                        str(item.get("week_range")).strip()
                        if item.get("week_range") is not None
                        else f"{request.week}주차"
                    ),
                    confidence=(
                        float(confidence) if confidence is not None else None
                    ),
                )
            )

        if not candidates and support_status == SUPPORTED_STATUS:
            raise ClassroomMaterialIngestEmptyScopeDomainException()
        return ClassroomMaterialIngestResult(
            scope_candidates=candidates[:5],
            extracted_chunks=extracted_chunks,
            support_status=support_status,
        )

    def _extract_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> tuple[list[ClassroomMaterialExtractedChunk], str]:
        if request.mime_type == "application/pdf":
            return self._extract_pdf_chunks(request), SUPPORTED_STATUS
        if self._is_youtube_link_request(request):
            return self._extract_youtube_link_chunks(
                request
            ), PARTIAL_SUPPORTED_STATUS
        if self._is_zip_mime_type(request.mime_type):
            return self._extract_zip_chunks(request), PARTIAL_SUPPORTED_STATUS
        if request.mime_type in TEXT_MIME_TYPES:
            return self._extract_plain_text_chunks(request), SUPPORTED_STATUS
        if request.mime_type in OFFICE_MIME_TYPES:
            return self._extract_office_placeholder_chunks(
                request
            ), PARTIAL_SUPPORTED_STATUS
        if request.mime_type.startswith(VIDEO_MIME_PREFIXES):
            return self._extract_media_placeholder_chunks(
                request
            ), PARTIAL_SUPPORTED_STATUS
        return [], UNSUPPORTED_STATUS

    def _extract_pdf_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> list[ClassroomMaterialExtractedChunk]:
        try:
            pages = PdfReader(BytesIO(request.content)).pages
        except Exception as exc:
            raise ClassroomMaterialIngestDomainException(
                message="PDF 강의 자료를 해석하지 못했습니다."
            ) from exc

        extracted_pages: list[dict[str, object]] = []
        for page_number, page in enumerate(pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                extracted_pages.append({
                    "page": page_number,
                    "text": text.strip(),
                })

        chunks: list[ClassroomMaterialExtractedChunk] = []
        chunk_index = 0
        for page in extracted_pages:
            page_number = int(page["page"])
            text = str(page["text"])
            for chunk_text in self._split_text(text):
                chunks.append(
                    ClassroomMaterialExtractedChunk(
                        text=chunk_text,
                        source_type="pdf",
                        source_unit_type="page",
                        citation_label=f"p.{page_number}",
                        chunk_index=chunk_index,
                        source_locator={"page": page_number},
                    )
                )
                chunk_index += 1
        return chunks

    def _extract_plain_text_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> list[ClassroomMaterialExtractedChunk]:
        text = request.content.decode("utf-8", errors="ignore").strip()
        chunks: list[ClassroomMaterialExtractedChunk] = []
        for chunk_index, chunk_text in enumerate(self._split_text(text)):
            chunks.append(
                ClassroomMaterialExtractedChunk(
                    text=chunk_text,
                    source_type="text",
                    source_unit_type="document",
                    citation_label=request.file_name,
                    chunk_index=chunk_index,
                    source_locator={"file_name": request.file_name},
                )
            )
        return chunks

    def _extract_zip_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> list[ClassroomMaterialExtractedChunk]:
        try:
            archive = ZipFile(BytesIO(request.content))
        except BadZipFile as exc:
            raise ClassroomMaterialIngestDomainException(
                message="ZIP 강의 자료를 해석하지 못했습니다."
            ) from exc

        chunks: list[ClassroomMaterialExtractedChunk] = []
        chunk_index = 0
        with archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if not self._is_text_file_name(info.filename):
                    continue
                try:
                    raw = archive.read(info)
                except Exception:
                    continue
                text = raw.decode("utf-8", errors="ignore").strip()
                for chunk_text in self._split_text(text):
                    chunks.append(
                        ClassroomMaterialExtractedChunk(
                            text=chunk_text,
                            source_type="zip_text",
                            source_unit_type="file",
                            citation_label=info.filename,
                            chunk_index=chunk_index,
                            source_locator={"archive_path": info.filename},
                        )
                    )
                    chunk_index += 1
        return chunks

    def _extract_youtube_link_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> list[ClassroomMaterialExtractedChunk]:
        locator = (
            request.source_url
            or request.content.decode("utf-8", errors="ignore").strip()
        )
        placeholder = (
            "YouTube 링크형 강의 자료입니다. 현재 transcript 자동 수집은 "
            "연결되지 않았으며, 링크 메타데이터만 보존합니다. "
            "transcript와 timestamp가 연결되면 같은 source_locator에 "
            "확장 가능합니다."
        )
        return [
            ClassroomMaterialExtractedChunk(
                text=placeholder,
                source_type="youtube",
                source_unit_type="transcript_segment",
                citation_label=request.title,
                chunk_index=0,
                source_locator={
                    "url": locator,
                    "has_transcript": False,
                },
            )
        ]

    def _extract_office_placeholder_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> list[ClassroomMaterialExtractedChunk]:
        placeholder = (
            f"{request.file_name} 문서는 현재 본문 추출기가 연결되지 "
            "않았습니다. 파일 메타데이터만 보존했으며, 추후 문서 텍스트 "
            "추출 전략으로 대체할 수 있습니다."
        )
        return [
            ClassroomMaterialExtractedChunk(
                text=placeholder,
                source_type="office_document",
                source_unit_type="document",
                citation_label=request.file_name,
                chunk_index=0,
                source_locator={
                    "file_name": request.file_name,
                    "mime_type": request.mime_type,
                    "extraction": "placeholder",
                },
            )
        ]

    def _extract_media_placeholder_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> list[ClassroomMaterialExtractedChunk]:
        placeholder = (
            f"{request.file_name} 미디어 자료입니다. 현재 원본 "
            "비디오/오디오 다운로드 및 transcript 추출은 수행하지 않고, "
            "transcript/timestamp 확장을 위한 placeholder만 저장합니다."
        )
        return [
            ClassroomMaterialExtractedChunk(
                text=placeholder,
                source_type="media",
                source_unit_type="transcript_segment",
                citation_label=request.file_name,
                chunk_index=0,
                source_locator={
                    "file_name": request.file_name,
                    "mime_type": request.mime_type,
                    "has_transcript": False,
                },
            )
        ]

    def _split_text(self, text: str) -> Iterable[str]:
        normalized = text.strip()
        if not normalized:
            return []

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            chunk_text = normalized[start : start + MAX_CHUNK_LENGTH].strip()
            if chunk_text:
                chunks.append(chunk_text)
            if start + MAX_CHUNK_LENGTH >= len(normalized):
                break
            start += MAX_CHUNK_LENGTH - CHUNK_OVERLAP
        return chunks

    def _is_youtube_link_request(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> bool:
        if request.source_kind is not ClassroomMaterialSourceKind.LINK:
            return False
        raw_text = (request.source_url or "").strip()
        if not raw_text:
            raw_text = request.content.decode("utf-8", errors="ignore").strip()
        if not raw_text:
            return False
        lowered = raw_text.lower()
        return any(marker in lowered for marker in YOUTUBE_HOST_MARKERS)

    def _is_zip_mime_type(self, mime_type: str) -> bool:
        return mime_type in {
            "application/zip",
            "application/x-zip-compressed",
        }

    def _is_text_file_name(self, file_name: str) -> bool:
        lowered = file_name.lower()
        return lowered.endswith((".txt", ".md", ".csv", ".json", ".xml"))
