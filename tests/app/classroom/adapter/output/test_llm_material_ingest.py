import json
from io import BytesIO
from uuid import UUID

import pytest

from app.classroom.adapter.output.integration.llm_material_ingest import (
    LLMClassroomMaterialIngestAdapter,
)
from app.classroom.domain.exception import ClassroomMaterialIngestDomainException
from app.classroom.domain.service import ClassroomMaterialIngestRequest

MATERIAL_ID = UUID("11111111-1111-1111-1111-111111111111")
CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")


class FakePage:
    def __init__(self, text: str):
        self.text = text

    def extract_text(self):
        return self.text


class FakePdfReader:
    def __init__(self, stream):
        assert isinstance(stream, BytesIO)
        self.pages = [FakePage("머신러닝 개요와 지도학습"), FakePage("회귀와 분류")]


class FakeQdrantClient:
    def __init__(self, *, url: str):
        self.url = url
        self.created = []
        self.deleted = []
        self.upserts = []
        self.exists = False

    def collection_exists(self, _name: str) -> bool:
        return self.exists

    def create_collection(self, **kwargs):
        self.created.append(kwargs)
        self.exists = True

    def delete(self, **kwargs):
        self.deleted.append(kwargs)

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)


class FakeEmbeddingsAPI:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        data = []
        for _ in kwargs["input"]:
            item = type("Embedding", (), {"embedding": [0.1, 0.2, 0.3]})()
            data.append(item)
        return type("EmbeddingResponse", (), {"data": data})()


class FakeChatCompletionsAPI:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        message = type(
            "Message",
            (),
            {
                "content": json.dumps(
                    {
                        "candidates": [
                            {
                                "label": "1주차 핵심 개념",
                                "scope_text": "머신러닝 개요와 지도학습의 차이",
                                "keywords": ["머신러닝", "지도학습"],
                                "week_range": "1주차",
                                "confidence": 0.93,
                            }
                        ]
                    }
                )
            },
        )()
        choice = type("Choice", (), {"message": message})()
        return type("Completion", (), {"choices": [choice]})()


class FakeAsyncOpenAI:
    def __init__(self, *, api_key: str):
        self.api_key = api_key
        self.embeddings = FakeEmbeddingsAPI()
        self.chat = type(
            "ChatAPI",
            (),
            {"completions": FakeChatCompletionsAPI()},
        )()


@pytest.mark.asyncio
async def test_ingest_material_extracts_scope_candidates_and_upserts_chunks(
    monkeypatch,
):
    import app.classroom.adapter.output.integration.llm_material_ingest as module

    fake_qdrant = FakeQdrantClient(url="http://localhost:6333")

    monkeypatch.setattr(module, "PdfReader", FakePdfReader)
    monkeypatch.setattr(module, "QdrantClient", lambda **kwargs: fake_qdrant)
    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(module.config, "OPENAI_EMBEDDING_MODEL", "embed-model")
    monkeypatch.setattr(module.config, "OPENAI_EXAM_GENERATION_MODEL", "chat-model")
    monkeypatch.setattr(module.config, "QDRANT_COLLECTION_NAME", "lecture_materials")
    monkeypatch.setattr(module.config, "QDRANT_URL", "http://localhost:6333")

    adapter = LLMClassroomMaterialIngestAdapter()
    result = await adapter.ingest_material(
        request=ClassroomMaterialIngestRequest(
            material_id=MATERIAL_ID,
            classroom_id=CLASSROOM_ID,
            title="1주차 자료",
            week=1,
            description="머신러닝 입문",
            file_name="week1.pdf",
            mime_type="application/pdf",
            content=b"%PDF-1.4",
        )
    )

    assert len(result.scope_candidates) == 1
    assert result.scope_candidates[0].label == "1주차 핵심 개념"
    assert result.scope_candidates[0].keywords == ["머신러닝", "지도학습"]
    assert len(fake_qdrant.created) == 1
    assert len(fake_qdrant.deleted) == 1
    assert len(fake_qdrant.upserts) == 1
    points = fake_qdrant.upserts[0]["points"]
    assert len(points) == 2
    assert points[0].payload["material_id"] == str(MATERIAL_ID)
    assert points[0].payload["classroom_id"] == str(CLASSROOM_ID)
    assert points[0].payload["file_name"] == "week1.pdf"


@pytest.mark.asyncio
async def test_ingest_material_raises_when_openai_key_missing(monkeypatch):
    import app.classroom.adapter.output.integration.llm_material_ingest as module

    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "")

    adapter = LLMClassroomMaterialIngestAdapter()
    with pytest.raises(ClassroomMaterialIngestDomainException) as exc_info:
        await adapter.ingest_material(
            request=ClassroomMaterialIngestRequest(
                material_id=MATERIAL_ID,
                classroom_id=CLASSROOM_ID,
                title="1주차 자료",
                week=1,
                description=None,
                file_name="week1.pdf",
                mime_type="application/pdf",
                content=b"%PDF-1.4",
            )
        )

    assert exc_info.value.message == "문항 생성 환경이 올바르게 설정되지 않았습니다."


@pytest.mark.asyncio
async def test_ingest_material_raises_for_non_pdf(monkeypatch):
    import app.classroom.adapter.output.integration.llm_material_ingest as module

    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")

    adapter = LLMClassroomMaterialIngestAdapter()
    with pytest.raises(ClassroomMaterialIngestDomainException) as exc_info:
        await adapter.ingest_material(
            request=ClassroomMaterialIngestRequest(
                material_id=MATERIAL_ID,
                classroom_id=CLASSROOM_ID,
                title="1주차 자료",
                week=1,
                description=None,
                file_name="week1.txt",
                mime_type="text/plain",
                content=b"plain-text",
            )
        )

    assert exc_info.value.message == "PDF 형식의 강의 자료만 적재할 수 있습니다."


class EmptyPdfReader:
    def __init__(self, stream):
        assert isinstance(stream, BytesIO)
        self.pages = [FakePage("   "), FakePage("")]


@pytest.mark.asyncio
async def test_ingest_material_raises_when_pdf_has_no_extractable_text(monkeypatch):
    import app.classroom.adapter.output.integration.llm_material_ingest as module

    monkeypatch.setattr(module, "PdfReader", EmptyPdfReader)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")

    adapter = LLMClassroomMaterialIngestAdapter()
    with pytest.raises(ClassroomMaterialIngestDomainException) as exc_info:
        await adapter.ingest_material(
            request=ClassroomMaterialIngestRequest(
                material_id=MATERIAL_ID,
                classroom_id=CLASSROOM_ID,
                title="1주차 자료",
                week=1,
                description=None,
                file_name="week1.pdf",
                mime_type="application/pdf",
                content=b"%PDF-1.4",
            )
        )

    assert exc_info.value.message == "강의 자료에서 추출된 텍스트가 없습니다."
