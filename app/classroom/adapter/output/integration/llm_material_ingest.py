import json
from io import BytesIO
from uuid import uuid4

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
from app.classroom.domain.entity import ClassroomMaterialScopeCandidate
from app.classroom.domain.exception import (
    ClassroomMaterialIngestDomainException,
    ClassroomMaterialIngestEmptyScopeDomainException,
)
from app.classroom.domain.service import (
    ClassroomMaterialIngestPort,
    ClassroomMaterialIngestRequest,
    ClassroomMaterialIngestResult,
)
from core.config import config


class LLMClassroomMaterialIngestAdapter(ClassroomMaterialIngestPort):
    async def ingest_material(
        self,
        *,
        request: ClassroomMaterialIngestRequest,
    ) -> ClassroomMaterialIngestResult:
        if request.mime_type != "application/pdf":
            raise ClassroomMaterialIngestDomainException(
                message="PDF 형식의 강의 자료만 적재할 수 있습니다."
            )
        if not config.OPENAI_API_KEY:
            raise ClassroomMaterialIngestDomainException(
                message="강의 자료 적재 환경이 올바르게 설정되지 않았습니다."
            )

        try:
            pages = PdfReader(BytesIO(request.content)).pages
        except Exception as exc:
            raise ClassroomMaterialIngestDomainException(
                message="PDF 강의 자료를 해석하지 못했습니다."
            ) from exc
        extracted_pages = []
        for page_number, page in enumerate(pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                extracted_pages.append({
                    "page": page_number,
                    "text": text.strip(),
                })
        if not extracted_pages:
            raise ClassroomMaterialIngestDomainException(
                message="강의 자료에서 추출된 텍스트가 없습니다."
            )

        chunks = []
        for page in extracted_pages:
            page_number = page["page"]
            text = page["text"]
            start = 0
            chunk_index = 0
            while start < len(text):
                chunk_text = text[start : start + 1000].strip()
                if chunk_text:
                    chunks.append({
                        "page": page_number,
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                    })
                if start + 1000 >= len(text):
                    break
                start += 800
                chunk_index += 1
        if not chunks:
            raise ClassroomMaterialIngestDomainException(
                message="강의 자료를 검색 가능한 청크로 분할하지 못했습니다."
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
                input=[chunk["text"] for chunk in chunks],
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
                            "page": chunk["page"],
                            "chunk_index": chunk["chunk_index"],
                            "text": chunk["text"],
                        },
                    )
                    for chunk, embedding in zip(
                        chunks,
                        embeddings.data,
                        strict=True,
                    )
                ],
            )

            source_text = "\n".join(
                page["text"] for page in extracted_pages[:5]
            )[:6000]
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
                completion.choices[0].message.content
                or '{"candidates": []}'
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

        if not candidates:
            raise ClassroomMaterialIngestEmptyScopeDomainException()
        return ClassroomMaterialIngestResult(scope_candidates=candidates[:5])
