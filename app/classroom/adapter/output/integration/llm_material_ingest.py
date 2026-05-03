import asyncio
import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.classroom.adapter.output.integration.material_extractors import (
    extract_docx_chunks,
    extract_hwpx_chunks,
    extract_pdf_chunks,
    extract_pptx_chunks,
    extract_zip_chunks,
    split_text,
    validate_extracted_chunk_budget,
)
from app.classroom.adapter.output.integration.media_transcript import (
    FfmpegOpenAIMediaTranscriptExtractor,
    MediaTranscriptExtractorPort,
)
from app.classroom.adapter.output.integration.prompts import (
    MATERIAL_DESCRIPTION_SYSTEM_PROMPT,
    MATERIAL_SCOPE_CANDIDATES_SYSTEM_PROMPT,
    build_material_description_user_prompt,
    build_material_scope_candidates_user_prompt,
)
from app.classroom.adapter.output.integration.youtube_transcript import (
    YoutubeTranscriptExtractorPort,
    YtDlpYoutubeTranscriptExtractor,
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
TEXT_FILE_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".xml",
}

PDF_MIME_TYPES = {"application/pdf"}
DOCX_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
}
PPTX_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
}
HWPX_MIME_TYPES = {
    "application/haansofthwp",
    "application/haansofthwpx",
    "application/x-hwpml",
}
ZIP_MIME_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
}

MEDIA_MIME_TYPES = {
    "video/mp4",
    "video/x-msvideo",
    "video/avi",
    "application/x-troff-msvideo",
}
MEDIA_FILE_EXTENSIONS = {".mp4", ".avi"}

YOUTUBE_LINK_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}

SUPPORTED_STATUS = "supported"
PARTIAL_SUPPORTED_STATUS = "partial_supported"
UNSUPPORTED_STATUS = "unsupported"
MAX_SCOPE_SOURCE_LENGTH = 6000


class LLMClassroomMaterialIngestAdapter(ClassroomMaterialIngestPort):
    def __init__(
        self,
        *,
        youtube_transcript_extractor: (
            YoutubeTranscriptExtractorPort | None
        ) = None,
        media_transcript_extractor: MediaTranscriptExtractorPort | None = None,
    ) -> None:
        self._youtube_transcript_extractor = (
            youtube_transcript_extractor or YtDlpYoutubeTranscriptExtractor()
        )
        self._media_transcript_extractor = (
            media_transcript_extractor or FfmpegOpenAIMediaTranscriptExtractor()
        )

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
            extracted_chunks, support_status = await self._extract_chunks(
                request
            )
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
            collection_exists = await asyncio.to_thread(
                client.collection_exists,
                config.QDRANT_COLLECTION_NAME,
            )
            if not collection_exists:
                await asyncio.to_thread(
                    client.create_collection,
                    collection_name=config.QDRANT_COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=1536,
                        distance=Distance.COSINE,
                    ),
                )

            await asyncio.to_thread(
                client.delete,
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
            source_text = "\n".join(
                chunk.text for chunk in extracted_chunks[:5]
            )[:MAX_SCOPE_SOURCE_LENGTH]
            generated_description = await self._generate_description(
                openai_client=openai_client,
                request=request,
                source_text=source_text,
            )
            description_request = replace(
                request,
                description=generated_description,
            )
            embeddings = await openai_client.embeddings.create(
                model=config.OPENAI_EMBEDDING_MODEL,
                input=[chunk.text for chunk in extracted_chunks],
            )
            points = [
                PointStruct(
                    id=str(uuid4()),
                    vector=embedding.embedding,
                    payload={
                        "classroom_id": str(request.classroom_id),
                        "material_id": str(request.material_id),
                        "title": request.title,
                        "description": generated_description,
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
            ]
            await asyncio.to_thread(
                client.upsert,
                collection_name=config.QDRANT_COLLECTION_NAME,
                wait=True,
                points=points,
            )

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
                            request=description_request,
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
            generated_description=generated_description,
        )

    async def _generate_description(
        self,
        *,
        openai_client: AsyncOpenAI,
        request: ClassroomMaterialIngestRequest,
        source_text: str,
    ) -> str:
        completion = await openai_client.chat.completions.create(
            model=config.OPENAI_EXAM_GENERATION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": MATERIAL_DESCRIPTION_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_material_description_user_prompt(
                        request=request,
                        source_text=source_text,
                    ),
                },
            ],
        )
        raw_description = completion.choices[0].message.content or ""
        generated_description = self._normalize_generated_description(
            raw_description
        )
        return generated_description or self._build_fallback_description(
            request
        )

    def _normalize_generated_description(self, description: str) -> str:
        return " ".join(description.split())[:300]

    def _build_fallback_description(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> str:
        if request.source_kind is ClassroomMaterialSourceKind.LINK:
            return f"{request.title} 관련 참고 링크입니다."
        return f"{request.title} 강의자료입니다."

    async def _extract_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> tuple[list[ClassroomMaterialExtractedChunk], str]:
        file_extension = Path(request.file_name).suffix.lower()
        mime_type = request.mime_type
        if self._is_pdf_request(mime_type, file_extension):
            return (
                await asyncio.to_thread(
                    extract_pdf_chunks,
                    content=request.content,
                    file_name=request.file_name,
                ),
                SUPPORTED_STATUS,
            )
        if self._is_youtube_link_request(request):
            return await self._extract_youtube_link_chunks(
                request
            ), SUPPORTED_STATUS
        if request.source_kind is ClassroomMaterialSourceKind.LINK:
            return [], UNSUPPORTED_STATUS
        if self._is_docx_request(mime_type, file_extension):
            return (
                await asyncio.to_thread(
                    extract_docx_chunks,
                    content=request.content,
                    file_name=request.file_name,
                ),
                SUPPORTED_STATUS,
            )
        if self._is_pptx_request(mime_type, file_extension):
            return (
                await asyncio.to_thread(
                    extract_pptx_chunks,
                    content=request.content,
                    file_name=request.file_name,
                ),
                SUPPORTED_STATUS,
            )
        if self._is_hwpx_request(mime_type, file_extension):
            return (
                await asyncio.to_thread(
                    extract_hwpx_chunks,
                    content=request.content,
                    file_name=request.file_name,
                ),
                SUPPORTED_STATUS,
            )
        if self._is_zip_request(mime_type, file_extension):
            return (
                await asyncio.to_thread(
                    extract_zip_chunks,
                    content=request.content,
                    file_name=request.file_name,
                ),
                PARTIAL_SUPPORTED_STATUS,
            )
        if self._is_text_request(mime_type, file_extension):
            return self._extract_plain_text_chunks(request), SUPPORTED_STATUS
        if self._is_media_request(mime_type, file_extension):
            return await self._extract_media_transcript_chunks(
                request
            ), SUPPORTED_STATUS
        return [], UNSUPPORTED_STATUS

    def _extract_plain_text_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> list[ClassroomMaterialExtractedChunk]:
        text = request.content.decode("utf-8", errors="ignore").strip()
        chunks: list[ClassroomMaterialExtractedChunk] = []
        for chunk_index, chunk_text in enumerate(split_text(text)):
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
        validate_extracted_chunk_budget(chunks)
        return chunks

    async def _extract_youtube_link_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> list[ClassroomMaterialExtractedChunk]:
        url = (
            request.source_url
            or request.content.decode("utf-8", errors="ignore").strip()
        )
        segments = await asyncio.to_thread(
            self._youtube_transcript_extractor.extract_transcript,
            url=url,
        )
        chunks: list[ClassroomMaterialExtractedChunk] = []
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            chunks.append(
                ClassroomMaterialExtractedChunk(
                    text=text,
                    source_type="youtube",
                    source_unit_type="transcript_segment",
                    citation_label=(
                        f"{request.title} {segment.start_seconds:.1f}s"
                    ),
                    chunk_index=len(chunks),
                    source_locator={
                        "url": url,
                        "start_seconds": segment.start_seconds,
                        "duration_seconds": segment.duration_seconds,
                    },
                )
            )
        if not chunks:
            raise ClassroomMaterialIngestDomainException(
                message="YouTube transcript를 추출하지 못했습니다."
            )
        validate_extracted_chunk_budget(chunks)
        return chunks

    async def _extract_media_transcript_chunks(
        self,
        request: ClassroomMaterialIngestRequest,
    ) -> list[ClassroomMaterialExtractedChunk]:
        segments = await self._media_transcript_extractor.extract_transcript(
            content=request.content,
            file_name=request.file_name,
        )
        chunks: list[ClassroomMaterialExtractedChunk] = []
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            chunks.append(
                ClassroomMaterialExtractedChunk(
                    text=text,
                    source_type="media",
                    source_unit_type="transcript_segment",
                    citation_label=(
                        f"{request.file_name} {segment.start_seconds:.1f}s"
                    ),
                    chunk_index=len(chunks),
                    source_locator={
                        "file_name": request.file_name,
                        "start_seconds": segment.start_seconds,
                        "duration_seconds": segment.duration_seconds,
                    },
                )
            )
        if not chunks:
            raise ClassroomMaterialIngestDomainException(
                message="미디어 transcript를 추출하지 못했습니다."
            )
        validate_extracted_chunk_budget(chunks)
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
        parsed = urlparse(raw_text)
        host = parsed.hostname or ""
        return parsed.scheme == "https" and host.lower() in YOUTUBE_LINK_HOSTS

    def _is_text_request(self, mime_type: str, file_extension: str) -> bool:
        return (
            mime_type in TEXT_MIME_TYPES
            or file_extension in TEXT_FILE_EXTENSIONS
        )

    def _is_pdf_request(self, mime_type: str, file_extension: str) -> bool:
        return mime_type in PDF_MIME_TYPES or file_extension == ".pdf"

    def _is_docx_request(self, mime_type: str, file_extension: str) -> bool:
        return mime_type in DOCX_MIME_TYPES or file_extension == ".docx"

    def _is_pptx_request(self, mime_type: str, file_extension: str) -> bool:
        return mime_type in PPTX_MIME_TYPES or file_extension == ".pptx"

    def _is_hwpx_request(self, mime_type: str, file_extension: str) -> bool:
        return mime_type in HWPX_MIME_TYPES or file_extension == ".hwpx"

    def _is_zip_request(self, mime_type: str, file_extension: str) -> bool:
        return mime_type in ZIP_MIME_TYPES or file_extension == ".zip"

    def _is_media_request(self, mime_type: str, file_extension: str) -> bool:
        return (
            mime_type in MEDIA_MIME_TYPES
            or file_extension in MEDIA_FILE_EXTENSIONS
        )
