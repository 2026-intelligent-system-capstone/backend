import json

from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.exam.domain.entity import BloomLevel, ExamDifficulty
from app.exam.domain.service import (
    ExamQuestionGenerationPort,
    GenerateExamQuestionsRequest,
    GeneratedExamQuestionDraft,
)
from core.config import config


class LLMExamQuestionGenerationAdapter(ExamQuestionGenerationPort):
    async def generate_questions(
        self,
        *,
        request: GenerateExamQuestionsRequest,
    ) -> list[GeneratedExamQuestionDraft]:
        if not config.LLM_INTEGRATION_ENABLED:
            raise RuntimeError("llm integration disabled")

        client = QdrantClient(url=config.QDRANT_URL)
        if not client.collection_exists(config.QDRANT_COLLECTION_NAME):
            raise RuntimeError("qdrant collection unavailable")

        openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        query_embedding = await openai_client.embeddings.create(
            model=config.OPENAI_EMBEDDING_MODEL,
            input=request.scope_text,
        )

        must = [
            FieldCondition(
                key="classroom_id",
                match=MatchValue(value=str(request.classroom_id)),
            )
        ]
        query_filter = Filter(must=must)
        if request.source_materials:
            query_filter.should = [
                FieldCondition(
                    key="material_id",
                    match=MatchValue(value=str(material.material_id)),
                )
                for material in request.source_materials
            ]

        hits = client.query_points(
            collection_name=config.QDRANT_COLLECTION_NAME,
            query=query_embedding.data[0].embedding,
            query_filter=query_filter,
            with_payload=True,
            limit=max(request.total_questions * 4, 8),
        ).points
        if not hits:
            raise RuntimeError("retrieval context unavailable")

        distribution: dict[BloomLevel, int] = {}
        assigned = 0
        for item in request.bloom_ratios:
            count = round(request.total_questions * item.percentage / 100)
            distribution[item.bloom_level] = count
            assigned += count
        diff = request.total_questions - assigned
        if diff != 0:
            largest = max(
                request.bloom_ratios,
                key=lambda item: item.percentage,
            )
            distribution[largest.bloom_level] = (
                distribution.get(largest.bloom_level, 0) + diff
            )

        context = "\n\n---\n\n".join(
            (
                f"[자료: {hit.payload.get('title')}, 파일: {hit.payload.get('file_name')}, "
                f"주차: {hit.payload.get('week')}, 페이지: {hit.payload.get('page')}]\n"
                f"{hit.payload.get('text', '')}"
            )
            for hit in hits
        )
        criteria = "\n".join(
            (
                f"- {criterion.title} ({criterion.weight}%): "
                f"{criterion.description or '설명 없음'}"
            )
            for criterion in request.criteria
        )
        bloom_plan = "\n".join(
            f"- {level.value}: {count}문항"
            for level, count in distribution.items()
            if count > 0
        )
        source_materials = "\n".join(
            (
                f"- {material.title} ({material.week}주차, "
                f"file: {material.file_name}, id: {material.material_id})"
            )
            for material in request.source_materials
        )

        completion = await openai_client.chat.completions.create(
            model=config.OPENAI_EXAM_GENERATION_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 대학 구술시험 문항을 생성하는 출제자입니다. "
                        "반드시 JSON만 응답하세요. 형식은 {\"questions\": [...]} 입니다. "
                        "각 문항은 question_number, bloom_level, difficulty, "
                        "question_text, scope_text, evaluation_objective, answer_key, "
                        "scoring_criteria, source_material_ids를 포함해야 합니다. "
                        "bloom_level은 none, remember, understand, apply, analyze, "
                        "evaluate, create 중 하나여야 하고, difficulty는 easy, medium, "
                        "hard 중 하나여야 합니다. question_number는 1부터 순서대로 "
                        "부여하세요."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"시험 제목: {request.title}\n"
                        f"시험 유형: {request.exam_type.value}\n"
                        f"시험 범위: {request.scope_text}\n"
                        f"난이도: {request.difficulty.value}\n"
                        f"최대 꼬리질문 수: {request.max_follow_ups}\n\n"
                        "평가 기준:\n"
                        f"{criteria}\n\n"
                        "Bloom 단계별 문항 수:\n"
                        f"{bloom_plan}\n\n"
                        "선택 자료:\n"
                        f"{source_materials or '지정 자료 없음'}\n\n"
                        "검색된 강의 자료 문맥:\n"
                        f"{context[:12000]}"
                    ),
                },
            ],
        )
        content = completion.choices[0].message.content or '{"questions": []}'
        parsed = json.loads(content)
        questions = parsed.get("questions", [])
        if len(questions) != request.total_questions:
            raise RuntimeError("generated question count mismatch")

        drafts = []
        actual_distribution: dict[BloomLevel, int] = {}
        for item in questions:
            bloom_level = BloomLevel(str(item["bloom_level"]))
            actual_distribution[bloom_level] = (
                actual_distribution.get(bloom_level, 0) + 1
            )
            drafts.append(
                GeneratedExamQuestionDraft(
                    question_number=int(item["question_number"]),
                    bloom_level=bloom_level,
                    difficulty=ExamDifficulty(str(item["difficulty"])),
                    question_text=str(item["question_text"]).strip(),
                    scope_text=str(item["scope_text"]).strip(),
                    evaluation_objective=str(
                        item["evaluation_objective"]
                    ).strip(),
                    answer_key=str(item["answer_key"]).strip(),
                    scoring_criteria=str(item["scoring_criteria"]).strip(),
                    source_material_ids=[
                        material.material_id
                        for material in request.source_materials
                        if str(material.material_id)
                        in {
                            str(source_material_id)
                            for source_material_id in item.get(
                                "source_material_ids",
                                [],
                            )
                        }
                    ],
                )
            )

        for level, expected_count in distribution.items():
            if actual_distribution.get(level, 0) != expected_count:
                raise RuntimeError("generated bloom distribution mismatch")
        return drafts
