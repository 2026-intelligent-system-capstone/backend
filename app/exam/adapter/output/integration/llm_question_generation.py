import asyncio
import json
from collections.abc import Sequence
from json import JSONDecodeError
from uuid import UUID

from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.exam.adapter.output.integration.prompts import (
    EXAM_QUESTION_GENERATION_SYSTEM_PROMPT,
    build_exam_question_generation_user_prompt,
)
from app.exam.application.exception import (
    ExamQuestionGenerationContextUnavailableException,
    ExamQuestionGenerationFailedException,
    ExamQuestionGenerationUnavailableException,
)
from app.exam.domain.entity import BloomLevel, ExamDifficulty
from app.exam.domain.service import (
    ExamQuestionGenerationPort,
    GeneratedExamQuestionDraft,
    GenerateExamQuestionsRequest,
)
from core.config import config


class LLMExamQuestionGenerationAdapter(ExamQuestionGenerationPort):
    async def generate_questions(
        self,
        *,
        request: GenerateExamQuestionsRequest,
    ) -> list[GeneratedExamQuestionDraft]:
        if not config.OPENAI_API_KEY:
            raise ExamQuestionGenerationUnavailableException(
                message=(
                    "OPENAI_API_KEY가 설정되지 않아 문항을 생성할 수 없습니다."
                )
            )

        client = QdrantClient(url=config.QDRANT_URL)
        collection_exists = await asyncio.to_thread(
            client.collection_exists,
            config.QDRANT_COLLECTION_NAME,
        )
        if not collection_exists:
            raise ExamQuestionGenerationUnavailableException(
                message="문항 생성을 위한 강의 자료 저장소를 찾을 수 없습니다."
            )

        openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        query_embedding = await openai_client.embeddings.create(
            model=config.OPENAI_EMBEDDING_MODEL,
            input=request.scope_text,
        )

        distribution = self._build_distribution(request)
        total_questions = sum(distribution.values())
        allowed_material_ids = {
            str(material.material_id): material.material_id
            for material in request.source_materials
        }
        hits = await self._retrieve_hits(
            client=client,
            request=request,
            query_embedding=query_embedding.data[0].embedding,
            allowed_material_ids=set(allowed_material_ids),
        )
        if not hits:
            raise ExamQuestionGenerationContextUnavailableException()

        context = self._build_context(hits)
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

        user_prompt = build_exam_question_generation_user_prompt(
            request=request,
            criteria_text=criteria,
            bloom_plan_text=bloom_plan,
            source_materials_text=source_materials,
            context=context[:12000],
        )

        last_error: Exception | None = None
        for _ in range(3):
            try:
                completion = await openai_client.chat.completions.create(
                    model=config.OPENAI_EXAM_GENERATION_MODEL,
                    response_format={"type": "json_object"},
                    messages=[
                        {
                            "role": "system",
                            "content": EXAM_QUESTION_GENERATION_SYSTEM_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                )
                content = (
                    completion.choices[0].message.content or '{"questions": []}'
                )
                drafts = self._parse_and_validate_questions(
                    content=content,
                    request=request,
                    total_questions=total_questions,
                    distribution=distribution,
                    allowed_material_ids=allowed_material_ids,
                )
                return drafts
            except ExamQuestionGenerationFailedException as exc:
                last_error = exc

        raise ExamQuestionGenerationFailedException() from last_error

    async def _retrieve_hits(
        self,
        *,
        client: QdrantClient,
        request: GenerateExamQuestionsRequest,
        query_embedding: Sequence[float],
        allowed_material_ids: set[str],
    ):
        if request.source_materials:
            hits = []
            per_material_limit = max(request.total_questions * 2, 4)
            for material in request.source_materials:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="classroom_id",
                            match=MatchValue(value=str(request.classroom_id)),
                        ),
                        FieldCondition(
                            key="material_id",
                            match=MatchValue(value=str(material.material_id)),
                        ),
                    ]
                )
                result = await asyncio.to_thread(
                    client.query_points,
                    collection_name=config.QDRANT_COLLECTION_NAME,
                    query=query_embedding,
                    query_filter=query_filter,
                    with_payload=True,
                    limit=per_material_limit,
                )
                hits.extend(result.points)
            return [
                hit
                for hit in hits
                if str(hit.payload.get("material_id")) in allowed_material_ids
            ]

        query_filter = Filter(
            must=[
                FieldCondition(
                    key="classroom_id",
                    match=MatchValue(value=str(request.classroom_id)),
                )
            ]
        )
        return (
            await asyncio.to_thread(
                client.query_points,
                collection_name=config.QDRANT_COLLECTION_NAME,
                query=query_embedding,
                query_filter=query_filter,
                with_payload=True,
                limit=max(request.total_questions * 4, 8),
            )
        ).points

    def _build_context(self, hits) -> str:
        grouped_hits: dict[str, list] = {}
        ordered_material_ids: list[str] = []
        for hit in hits:
            material_id = str(hit.payload.get("material_id") or "")
            if material_id not in grouped_hits:
                grouped_hits[material_id] = []
                ordered_material_ids.append(material_id)
            grouped_hits[material_id].append(hit)

        selected_hits = []
        while True:
            appended = False
            for material_id in ordered_material_ids:
                material_hits = grouped_hits[material_id]
                if not material_hits:
                    continue
                selected_hits.append(material_hits.pop(0))
                appended = True
            if not appended:
                break

        context_blocks = []
        current_length = 0
        for hit in selected_hits:
            block = (
                f"[자료: {hit.payload.get('title')}, "
                f"파일: {hit.payload.get('file_name')}, "
                f"주차: {hit.payload.get('week')}, "
                f"페이지: {hit.payload.get('page')}]\n"
                f"{str(hit.payload.get('text', '')).strip()}"
            )
            separator_length = 0 if not context_blocks else len("\n\n---\n\n")
            additional_length = separator_length + len(block)
            if current_length + additional_length > 12000:
                break
            context_blocks.append(block)
            current_length += additional_length

        return "\n\n---\n\n".join(context_blocks)

    def _build_distribution(
        self,
        request: GenerateExamQuestionsRequest,
    ) -> dict[BloomLevel, int]:
        return {
            item.bloom_level: item.count for item in request.bloom_counts
        }

    def _parse_and_validate_questions(
        self,
        *,
        content: str,
        request: GenerateExamQuestionsRequest,
        total_questions: int,
        distribution: dict[BloomLevel, int],
        allowed_material_ids: dict[str, UUID],
    ) -> list[GeneratedExamQuestionDraft]:
        try:
            parsed = json.loads(self._strip_code_block(content))
        except JSONDecodeError as exc:
            raise ExamQuestionGenerationFailedException() from exc

        questions = parsed.get("questions")
        if not isinstance(questions, list):
            raise ExamQuestionGenerationFailedException()
        if len(questions) != total_questions:
            raise ExamQuestionGenerationFailedException()

        drafts = [
            self._normalize_question(
                index=index,
                item=item,
                request=request,
                allowed_material_ids=allowed_material_ids,
            )
            for index, item in enumerate(questions, start=1)
        ]
        self._validate_distribution(drafts=drafts, distribution=distribution)
        self._validate_duplicates(drafts)
        return drafts

    def _normalize_question(
        self,
        *,
        index: int,
        item: dict,
        request: GenerateExamQuestionsRequest,
        allowed_material_ids: dict[str, UUID],
    ) -> GeneratedExamQuestionDraft:
        try:
            bloom_level = BloomLevel(str(item["bloom_level"]).strip())
            difficulty = ExamDifficulty(str(item["difficulty"]).strip())
            question_text = str(item["question_text"]).strip()
            scope_text = str(item["scope_text"]).strip()
            evaluation_objective = str(item["evaluation_objective"]).strip()
            answer_key = str(item["answer_key"]).strip()
            scoring_criteria = str(item["scoring_criteria"]).strip()
        except (KeyError, ValueError, TypeError) as exc:
            raise ExamQuestionGenerationFailedException() from exc

        if difficulty is not request.difficulty:
            raise ExamQuestionGenerationFailedException()
        if not all([
            question_text,
            scope_text,
            evaluation_objective,
            answer_key,
            scoring_criteria,
        ]):
            raise ExamQuestionGenerationFailedException()

        filtered_source_material_ids = []
        for source_material_id in item.get("source_material_ids", []):
            material_id = allowed_material_ids.get(str(source_material_id))
            if material_id is not None:
                filtered_source_material_ids.append(material_id)

        if request.source_materials and not filtered_source_material_ids:
            raise ExamQuestionGenerationFailedException()

        return GeneratedExamQuestionDraft(
            question_number=index,
            bloom_level=bloom_level,
            difficulty=difficulty,
            question_text=question_text,
            scope_text=scope_text,
            evaluation_objective=evaluation_objective,
            answer_key=answer_key,
            scoring_criteria=scoring_criteria,
            source_material_ids=filtered_source_material_ids,
        )

    def _validate_distribution(
        self,
        *,
        drafts: list[GeneratedExamQuestionDraft],
        distribution: dict[BloomLevel, int],
    ) -> None:
        actual_distribution: dict[BloomLevel, int] = {}
        for draft in drafts:
            actual_distribution[draft.bloom_level] = (
                actual_distribution.get(draft.bloom_level, 0) + 1
            )
        for level, expected_count in distribution.items():
            if actual_distribution.get(level, 0) != expected_count:
                raise ExamQuestionGenerationFailedException()

    def _validate_duplicates(
        self,
        drafts: list[GeneratedExamQuestionDraft],
    ) -> None:
        normalized_texts = {
            " ".join(draft.question_text.lower().split()) for draft in drafts
        }
        if len(normalized_texts) != len(drafts):
            raise ExamQuestionGenerationFailedException()

    def _strip_code_block(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```json"):
            return stripped.removeprefix("```json").removesuffix("```").strip()
        if stripped.startswith("```"):
            return stripped.removeprefix("```").removesuffix("```").strip()
        return stripped
