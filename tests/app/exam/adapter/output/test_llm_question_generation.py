import json
from uuid import UUID

import pytest

from app.exam.adapter.output.integration.llm_question_generation import (
    LLMExamQuestionGenerationAdapter,
)
from app.exam.domain.entity import BloomLevel, ExamDifficulty, ExamType
from app.exam.domain.service import (
    ExamQuestionGenerationCriterion,
    ExamQuestionGenerationRatio,
    ExamQuestionSourceMaterial,
    GenerateExamQuestionsRequest,
)

CLASSROOM_ID = UUID("11111111-1111-1111-1111-111111111111")
EXAM_ID = UUID("22222222-2222-2222-2222-222222222222")
MATERIAL_ID = UUID("33333333-3333-3333-3333-333333333333")


class FakeQdrantClient:
    def __init__(self, *, url: str):
        self.url = url
        self.query_calls = []

    def collection_exists(self, _name: str) -> bool:
        return True

    def query_points(self, **kwargs):
        self.query_calls.append(kwargs)
        point = type(
            "Point",
            (),
            {
                "payload": {
                    "title": "1주차 자료",
                    "file_name": "week1.pdf",
                    "week": 1,
                    "page": 1,
                    "text": "머신러닝 개요와 지도학습, 회귀와 분류",
                }
            },
        )()
        return type("QueryResult", (), {"points": [point]})()


class FakeEmbeddingsAPI:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = type("Embedding", (), {"embedding": [0.1, 0.2, 0.3]})()
        return type("EmbeddingResponse", (), {"data": [item]})()


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
                        "questions": [
                            {
                                "question_number": 1,
                                "bloom_level": "apply",
                                "difficulty": "medium",
                                "question_text": "회귀와 분류의 차이를 설명해주세요.",
                                "scope_text": "1주차 머신러닝 기초",
                                "evaluation_objective": "지도학습의 핵심 구분 능력 평가",
                                "answer_key": "출력 형태와 학습 목표 차이를 포함해야 합니다.",
                                "scoring_criteria": "핵심 개념과 예시를 말하면 정답입니다.",
                                "source_material_ids": [str(MATERIAL_ID)],
                            },
                            {
                                "question_number": 2,
                                "bloom_level": "analyze",
                                "difficulty": "medium",
                                "question_text": "지도학습과 비지도학습의 차이를 비교해주세요.",
                                "scope_text": "1주차 머신러닝 기초",
                                "evaluation_objective": "학습 방식 차이 분석 능력 평가",
                                "answer_key": "정답 데이터 유무와 활용 사례 차이를 포함해야 합니다.",
                                "scoring_criteria": "핵심 비교 기준을 2개 이상 제시하면 정답입니다.",
                                "source_material_ids": [str(MATERIAL_ID)],
                            },
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
async def test_generate_questions_returns_backend_drafts(monkeypatch):
    import app.exam.adapter.output.integration.llm_question_generation as module

    fake_qdrant = FakeQdrantClient(url="http://localhost:6333")

    monkeypatch.setattr(module, "QdrantClient", lambda **kwargs: fake_qdrant)
    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.config, "LLM_INTEGRATION_ENABLED", True)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(module.config, "OPENAI_EMBEDDING_MODEL", "embed-model")
    monkeypatch.setattr(module.config, "OPENAI_EXAM_GENERATION_MODEL", "chat-model")
    monkeypatch.setattr(module.config, "QDRANT_COLLECTION_NAME", "lecture_materials")
    monkeypatch.setattr(module.config, "QDRANT_URL", "http://localhost:6333")

    adapter = LLMExamQuestionGenerationAdapter()
    drafts = await adapter.generate_questions(
        request=GenerateExamQuestionsRequest(
            exam_id=EXAM_ID,
            classroom_id=CLASSROOM_ID,
            title="중간 평가",
            exam_type=ExamType.MIDTERM,
            scope_text="1주차 머신러닝 기초",
            total_questions=2,
            max_follow_ups=2,
            difficulty=ExamDifficulty.MEDIUM,
            criteria=[
                ExamQuestionGenerationCriterion(
                    title="개념 이해",
                    description="핵심 개념을 정확히 설명하는지 평가",
                    weight=100,
                )
            ],
            bloom_ratios=[
                ExamQuestionGenerationRatio(
                    bloom_level=BloomLevel.APPLY,
                    percentage=50,
                ),
                ExamQuestionGenerationRatio(
                    bloom_level=BloomLevel.ANALYZE,
                    percentage=50,
                ),
            ],
            source_materials=[
                ExamQuestionSourceMaterial(
                    material_id=MATERIAL_ID,
                    file_name="week1.pdf",
                    title="1주차 자료",
                    week=1,
                )
            ],
        )
    )

    assert len(drafts) == 2
    assert drafts[0].bloom_level is BloomLevel.APPLY
    assert drafts[1].bloom_level is BloomLevel.ANALYZE
    assert drafts[0].difficulty is ExamDifficulty.MEDIUM
    assert drafts[0].source_material_ids == [MATERIAL_ID]
    assert fake_qdrant.query_calls[0]["limit"] == 8


@pytest.mark.asyncio
async def test_generate_questions_raises_when_disabled(monkeypatch):
    import app.exam.adapter.output.integration.llm_question_generation as module

    monkeypatch.setattr(module.config, "LLM_INTEGRATION_ENABLED", False)

    adapter = LLMExamQuestionGenerationAdapter()
    with pytest.raises(RuntimeError):
        await adapter.generate_questions(
            request=GenerateExamQuestionsRequest(
                exam_id=EXAM_ID,
                classroom_id=CLASSROOM_ID,
                title="중간 평가",
                exam_type=ExamType.MIDTERM,
                scope_text="1주차 머신러닝 기초",
                total_questions=1,
                max_follow_ups=2,
                difficulty=ExamDifficulty.MEDIUM,
                criteria=[],
                bloom_ratios=[
                    ExamQuestionGenerationRatio(
                        bloom_level=BloomLevel.APPLY,
                        percentage=100,
                    )
                ],
                source_materials=[],
            )
        )
