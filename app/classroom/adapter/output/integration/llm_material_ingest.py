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

from app.classroom.domain.entity import ClassroomMaterialScopeCandidate
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
        if not config.LLM_INTEGRATION_ENABLED:
            return ClassroomMaterialIngestResult()
        if request.mime_type != "application/pdf":
            return ClassroomMaterialIngestResult()

        pages = PdfReader(BytesIO(request.content)).pages
        page_texts = []
        for page in pages:
            text = page.extract_text()
            if text and text.strip():
                page_texts.append(text.strip())
        if not page_texts:
            return ClassroomMaterialIngestResult()

        chunks = []
        for page_number, text in enumerate(page_texts, start=1):
            start = 0
            chunk_index = 0
            while start < len(text):
                chunk_text = text[start : start + 1000].strip()
                if chunk_text:
                    chunks.append(
                        {
                            "page": page_number,
                            "chunk_index": chunk_index,
                            "text": chunk_text,
                        }
                    )
                if start + 1000 >= len(text):
                    break
                start += 800
                chunk_index += 1
        if not chunks:
            return ClassroomMaterialIngestResult()

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

        completion = await openai_client.chat.completions.create(
            model=config.OPENAI_EXAM_GENERATION_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 강의 자료에서 교수자가 시험 범위로 선택할 수 있는 "
                        "후보 범위를 추출하는 도우미입니다. 반드시 JSON만 "
                        "응답하세요. 형식은 {\"candidates\": [...]} 입니다. "
                        "각 후보는 label, scope_text, keywords, week_range, "
                        "confidence를 포함해야 합니다. 후보는 1~5개만 생성하고, "
                        "scope_text는 400자 이내로 요약하세요."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"자료 제목: {request.title}\n"
                        f"자료 설명: {request.description or '없음'}\n"
                        f"주차: {request.week}\n"
                        f"파일명: {request.file_name}\n\n"
                        "강의 자료 본문:\n"
                        f"{chr(10).join(page_texts[:5])[:6000]}"
                    ),
                },
            ],
        )
        content = completion.choices[0].message.content or '{"candidates": []}'
        parsed = json.loads(content)

        candidates = []
        for item in parsed.get("candidates", []):
            label = str(item.get("label") or "").strip()
            scope_text = str(item.get("scope_text") or "").strip()
            if not label or not scope_text:
                continue
            keywords = [
                str(keyword).strip()
                for keyword in item.get("keywords", [])
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
                        float(confidence)
                        if confidence is not None
                        else None
                    ),
                )
            )

        if not candidates:
            raise RuntimeError("scope candidate extraction failed")
        return ClassroomMaterialIngestResult(scope_candidates=candidates[:5])
