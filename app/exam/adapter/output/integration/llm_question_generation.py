import asyncio
import json
import math
from collections.abc import Sequence
from json import JSONDecodeError
from uuid import UUID

from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.exam.adapter.output.integration.prompts import (
    EXAM_QUESTION_GENERATION_SYSTEM_PROMPT,
    build_multiple_choice_question_generation_user_prompt,
    build_oral_question_generation_user_prompt,
    build_subjective_question_generation_user_prompt,
)
from app.exam.application.exception import (
    ExamQuestionGenerationContextUnavailableException,
    ExamQuestionGenerationFailedException,
    ExamQuestionGenerationUnavailableException,
)
from app.exam.domain.entity import (
    BloomLevel,
    ExamQuestionAnswerKey,
    ExamQuestionAnswerOption,
    ExamQuestionRubric,
    ExamQuestionRubricCriterion,
    ExamQuestionType,
)
from app.exam.domain.service import (
    ExamQuestionGenerationPort,
    GeneratedExamQuestionDraft,
    GenerateExamQuestionsRequest,
)
from core.config import config

QUESTION_TEXT_MAX_LENGTH = 5000
INTENT_TEXT_MAX_LENGTH = 5000
RUBRIC_TEXT_MAX_LENGTH = 12000
CORRECT_ANSWER_TEXT_MAX_LENGTH = 2000


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

        bloom_distribution = self._build_bloom_distribution(request)
        question_type_distribution = self._build_question_type_distribution(
            request
        )
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
        source_materials = "\n".join(
            (
                f"- {material.title} ({material.week}주차, "
                f"file: {material.file_name}, id: {material.material_id})"
            )
            for material in request.source_materials
        )

        prompt_builders = {
            ExamQuestionType.MULTIPLE_CHOICE: (
                build_multiple_choice_question_generation_user_prompt
            ),
            ExamQuestionType.SUBJECTIVE: (
                build_subjective_question_generation_user_prompt
            ),
            ExamQuestionType.ORAL: build_oral_question_generation_user_prompt,
        }
        all_drafts: list[GeneratedExamQuestionDraft] = []
        bloom_offset = 0

        for question_type, count in question_type_distribution.items():
            if count <= 0 or question_type is ExamQuestionType.NONE:
                continue
            type_bloom_distribution = dict(
                self._slice_bloom_distribution(
                    bloom_distribution=bloom_distribution,
                    start=bloom_offset,
                    count=count,
                )
            )
            bloom_offset += count
            type_prompt = prompt_builders[question_type](
                request=request,
                criteria_text=criteria,
                bloom_plan_text="\n".join(
                    f"- {level.value}: {level_count}문항"
                    for level, level_count in type_bloom_distribution.items()
                ),
                question_type_plan_text=f"- {question_type.value}: {count}문항",
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
                                "content": (
                                    EXAM_QUESTION_GENERATION_SYSTEM_PROMPT
                                ),
                            },
                            {
                                "role": "user",
                                "content": type_prompt,
                            },
                        ],
                    )
                    content = (
                        completion.choices[0].message.content
                        or '{"questions": []}'
                    )
                    all_drafts.extend(
                        self._parse_and_validate_questions(
                            content=content,
                            request=request,
                            total_questions=count,
                            bloom_distribution=type_bloom_distribution,
                            question_type_distribution={question_type: count},
                            allowed_material_ids=allowed_material_ids,
                        )
                    )
                    break
                except ExamQuestionGenerationFailedException as exc:
                    last_error = exc
            else:
                raise ExamQuestionGenerationFailedException() from last_error

        drafts = [
            GeneratedExamQuestionDraft(
                question_number=index,
                max_score=draft.max_score,
                question_type=draft.question_type,
                bloom_level=draft.bloom_level,
                difficulty=draft.difficulty,
                question_text=draft.question_text,
                intent_text=draft.intent_text,
                rubric_text=draft.rubric_text,
                answer_options=list(draft.answer_options),
                correct_answer_text=draft.correct_answer_text,
                answer_options_data=list(draft.answer_options_data),
                answer_key_data=draft.answer_key_data,
                rubric_data=draft.rubric_data,
                source_material_ids=list(draft.source_material_ids),
            )
            for index, draft in enumerate(all_drafts, start=1)
        ]
        self._validate_bloom_distribution(
            drafts=drafts,
            distribution=bloom_distribution,
        )
        self._validate_question_type_distribution(
            drafts=drafts,
            distribution=question_type_distribution,
        )
        self._validate_duplicates(drafts)
        return drafts

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
            block = self._build_context_block(hit.payload)
            separator_length = 0 if not context_blocks else len("\n\n---\n\n")
            additional_length = separator_length + len(block)
            if current_length + additional_length > 12000:
                break
            context_blocks.append(block)
            current_length += additional_length

        return "\n\n---\n\n".join(context_blocks)

    def _build_context_block(self, payload: dict[str, object]) -> str:
        title = str(payload.get("title") or "제목 없음")
        file_name = str(payload.get("file_name") or "파일명 없음")
        week = payload.get("week")
        source_type = str(payload.get("source_type") or "unknown")
        source_unit_type = str(payload.get("source_unit_type") or "unknown")
        citation_label = str(payload.get("citation_label") or "근거 위치 없음")
        support_status = str(payload.get("support_status") or "supported")
        text = str(payload.get("text", "")).strip()
        locator = payload.get("source_locator") or {}
        if isinstance(locator, dict):
            locator_text = ", ".join(
                f"{key}={value}" for key, value in locator.items()
            )
        else:
            locator_text = str(locator)

        return (
            f"[자료: {title}, 파일: {file_name}, 주차: {week}, "
            f"형식: {source_type}, 단위: {source_unit_type}, "
            f"인용: {citation_label}, 지원상태: {support_status}, "
            f"locator: {locator_text or '-'}]\n"
            f"{text}"
        )

    def _build_bloom_distribution(
        self,
        request: GenerateExamQuestionsRequest,
    ) -> dict[BloomLevel, int]:
        return {item.bloom_level: item.count for item in request.bloom_counts}

    def _build_question_type_distribution(
        self,
        request: GenerateExamQuestionsRequest,
    ) -> dict[ExamQuestionType, int]:
        return {
            item.question_type: item.count
            for item in request.question_type_counts
        }

    def _parse_and_validate_questions(
        self,
        *,
        content: str,
        request: GenerateExamQuestionsRequest,
        total_questions: int,
        bloom_distribution: dict[BloomLevel, int],
        question_type_distribution: dict[ExamQuestionType, int],
        allowed_material_ids: dict[str, UUID],
    ) -> list[GeneratedExamQuestionDraft]:
        try:
            parsed = json.loads(self._strip_code_block(content))
        except JSONDecodeError:
            parsed = {"questions": []}

        raw_questions = (
            parsed.get("questions") if isinstance(parsed, dict) else []
        )
        if not isinstance(raw_questions, list):
            raw_questions = []

        expected_bloom_levels = self._build_expected_bloom_levels(
            distribution=bloom_distribution,
            total_questions=total_questions,
        )
        expected_question_types = self._build_expected_question_types(
            distribution=question_type_distribution,
            total_questions=total_questions,
        )
        matching_questions = [
            item
            for item in raw_questions
            if isinstance(item, dict)
            and item.get("question_type") == expected_question_types[0].value
        ]
        if len(matching_questions) < total_questions:
            raise ExamQuestionGenerationFailedException()
        normalized_items = list(matching_questions[:total_questions])

        drafts = []
        for index, item in enumerate(normalized_items, start=1):
            raw_bloom_level = str(item.get("bloom_level") or "")
            if raw_bloom_level != expected_bloom_levels[index - 1].value:
                raise ExamQuestionGenerationFailedException()
            drafts.append(
                self._normalize_question(
                    index=index,
                    item=item,
                    request=request,
                    allowed_material_ids=allowed_material_ids,
                    expected_bloom_level=expected_bloom_levels[index - 1],
                    expected_question_type=expected_question_types[index - 1],
                )
            )
        self._validate_duplicate_question_texts(drafts)
        return drafts

    def _normalize_question(
        self,
        *,
        index: int,
        item: dict,
        request: GenerateExamQuestionsRequest,
        allowed_material_ids: dict[str, UUID],
        expected_bloom_level: BloomLevel,
        expected_question_type: ExamQuestionType,
    ) -> GeneratedExamQuestionDraft:
        max_score = self._coerce_positive_float(item.get("max_score"))
        question_text = str(item.get("question_text") or "").strip()
        intent_text = str(item.get("intent_text") or "").strip()
        rubric_text = str(item.get("rubric_text") or "").strip()

        if not question_text:
            question_text = (
                f"{request.scope_text} 범위의 핵심 개념을 본인의 말로 "
                "설명해주세요."
            )
        if not intent_text:
            intent_text = (
                f"{request.scope_text} 범위의 핵심 이해도를 평가합니다."
            )
        if not rubric_text:
            rubric_text = (
                "핵심 개념을 정확히 설명하고 근거를 함께 제시하면 "
                "좋은 답변입니다."
            )

        question_text = self._truncate_text(
            question_text,
            max_length=QUESTION_TEXT_MAX_LENGTH,
        )
        intent_text = self._truncate_text(
            intent_text,
            max_length=INTENT_TEXT_MAX_LENGTH,
        )
        rubric_text = self._truncate_text(
            rubric_text,
            max_length=RUBRIC_TEXT_MAX_LENGTH,
        )

        (
            question_type,
            answer_options,
            correct_answer_text,
            answer_options_data,
            answer_key_data,
            rubric_data,
        ) = self._coerce_question_answer_fields(
            expected_question_type=expected_question_type,
            raw_answer_options=item.get("answer_options"),
            raw_correct_answer_text=item.get("correct_answer_text"),
            raw_answer_key=item.get("answer_key")
            or item.get("answer_key_data"),
            raw_rubric=item.get("rubric") or item.get("rubric_data"),
        )

        return GeneratedExamQuestionDraft(
            question_number=index,
            max_score=max_score,
            question_type=question_type,
            bloom_level=expected_bloom_level,
            difficulty=request.difficulty,
            question_text=question_text,
            intent_text=intent_text,
            rubric_text=rubric_text,
            answer_options=answer_options,
            correct_answer_text=correct_answer_text,
            answer_options_data=answer_options_data,
            answer_key_data=answer_key_data,
            rubric_data=rubric_data,
            source_material_ids=self._normalize_source_material_ids(
                item=item,
                allowed_material_ids=allowed_material_ids,
            ),
        )

    def _slice_bloom_distribution(
        self,
        *,
        bloom_distribution: dict[BloomLevel, int],
        start: int,
        count: int,
    ) -> list[tuple[BloomLevel, int]]:
        levels = [
            level
            for level, level_count in bloom_distribution.items()
            for _ in range(max(level_count, 0))
        ]
        sliced_levels = levels[start : start + count]
        result: list[tuple[BloomLevel, int]] = []
        for level in sliced_levels:
            if result and result[-1][0] is level:
                result[-1] = (level, result[-1][1] + 1)
            else:
                result.append((level, 1))
        return result

    def _build_expected_bloom_levels(
        self,
        *,
        distribution: dict[BloomLevel, int],
        total_questions: int,
    ) -> list[BloomLevel]:
        levels = [
            level
            for level, count in distribution.items()
            for _ in range(max(count, 0))
        ]
        fallback_level = next(iter(distribution), BloomLevel.UNDERSTAND)
        while len(levels) < total_questions:
            levels.append(fallback_level)
        return levels[:total_questions]

    def _build_expected_question_types(
        self,
        *,
        distribution: dict[ExamQuestionType, int],
        total_questions: int,
    ) -> list[ExamQuestionType]:
        question_types = [
            question_type
            for question_type, count in distribution.items()
            for _ in range(max(count, 0))
            if question_type is not ExamQuestionType.NONE
        ]
        fallback_type = next(
            (
                question_type
                for question_type in distribution
                if question_type is not ExamQuestionType.NONE
            ),
            ExamQuestionType.ORAL,
        )
        while len(question_types) < total_questions:
            question_types.append(fallback_type)
        return question_types[:total_questions]

    def _build_fallback_question_item(
        self,
        *,
        request: GenerateExamQuestionsRequest,
        index: int,
    ) -> dict[str, object]:
        return {
            "max_score": 1.0,
            "question_text": (
                f"{request.scope_text} 범위에서 중요한 개념 하나를 골라 "
                "본인의 말로 설명해주세요."
            ),
            "intent_text": (
                f"{request.scope_text} 범위의 핵심 이해도를 평가합니다."
            ),
            "rubric_text": (
                "핵심 개념의 의미, 필요한 이유, 적용 맥락을 함께 "
                "설명하면 좋은 답변입니다."
            ),
            "answer_options": [],
            "correct_answer_text": None,
            "source_material_ids": [],
            "question_number": index,
        }

    def _coerce_positive_float(self, value: object) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return 1.0
        if not math.isfinite(result) or result <= 0:
            return 1.0
        return result

    def _truncate_text(self, value: str, *, max_length: int) -> str:
        if len(value) <= max_length:
            return value
        return value[:max_length].rstrip()

    def _coerce_question_answer_fields(
        self,
        *,
        expected_question_type: ExamQuestionType,
        raw_answer_options: object,
        raw_correct_answer_text: object,
        raw_answer_key: object,
        raw_rubric: object,
    ) -> tuple[
        ExamQuestionType,
        list[str],
        str | None,
        list[ExamQuestionAnswerOption],
        ExamQuestionAnswerKey | None,
        ExamQuestionRubric,
    ]:
        answer_options_data, option_id_map = self._parse_answer_options_data(
            raw_answer_options
        )
        answer_options = [option.text for option in answer_options_data]
        rubric_data = self._parse_rubric(raw_rubric)
        answer_key_data = self._parse_answer_key(
            expected_question_type=expected_question_type,
            raw_answer_key=raw_answer_key,
            option_id_map=option_id_map,
        )

        correct_answer_text = (
            str(raw_correct_answer_text).strip()
            if raw_correct_answer_text is not None
            and str(raw_correct_answer_text).strip()
            else None
        )
        if correct_answer_text is not None:
            correct_answer_text = self._truncate_text(
                correct_answer_text,
                max_length=CORRECT_ANSWER_TEXT_MAX_LENGTH,
            )

        if expected_question_type is ExamQuestionType.MULTIPLE_CHOICE:
            if answer_options_data and answer_key_data is not None:
                correct_ids = answer_key_data.correct_option_ids
                correct_options = [
                    option
                    for option in answer_options_data
                    if option.is_correct
                ]
                if (
                    len(correct_ids) == 1
                    and len(correct_options) == 1
                    and correct_ids[0] == correct_options[0].id
                ):
                    return (
                        ExamQuestionType.MULTIPLE_CHOICE,
                        answer_options,
                        correct_options[0].text,
                        answer_options_data,
                        answer_key_data,
                        rubric_data,
                    )
                raise ExamQuestionGenerationFailedException()
            raise ExamQuestionGenerationFailedException()

        if expected_question_type is ExamQuestionType.SUBJECTIVE:
            if (
                answer_key_data is None
                or not answer_key_data.model_answer
                or not answer_key_data.acceptable_answers
                or not answer_key_data.required_keywords
                or not rubric_data.criteria
            ):
                raise ExamQuestionGenerationFailedException()
            return (
                ExamQuestionType.SUBJECTIVE,
                [],
                answer_key_data.model_answer,
                [],
                answer_key_data,
                rubric_data,
            )

        if correct_answer_text is not None:
            raise ExamQuestionGenerationFailedException()
        if (
            answer_key_data is None
            or not answer_key_data.expected_points
            or not answer_key_data.follow_up_questions
            or not rubric_data.criteria
        ):
            raise ExamQuestionGenerationFailedException()
        return (
            ExamQuestionType.ORAL,
            [],
            None,
            [],
            answer_key_data,
            rubric_data,
        )

    def _parse_answer_options_data(
        self,
        raw_answer_options: object,
    ) -> tuple[list[ExamQuestionAnswerOption], dict[str, str]]:
        if not isinstance(raw_answer_options, list):
            return [], {}
        options = []
        option_id_map: dict[str, str] = {}
        seen_option_ids: set[str] = set()
        for index, raw_option in enumerate(raw_answer_options, start=1):
            if not isinstance(raw_option, dict):
                continue
            raw_option_id = str(raw_option.get("id") or "").strip()
            raw_label = str(raw_option.get("label") or "").strip()
            text = str(raw_option.get("text") or "").strip()
            if not raw_option_id or not raw_label or not text:
                raise ExamQuestionGenerationFailedException()
            if raw_option_id in seen_option_ids:
                raise ExamQuestionGenerationFailedException()
            seen_option_ids.add(raw_option_id)
            option_id = str(index)
            option_id_map[raw_option_id] = option_id
            options.append(
                ExamQuestionAnswerOption(
                    id=option_id,
                    label=option_id,
                    text=text,
                    is_correct=self._parse_bool(raw_option.get("is_correct")),
                    explanation=(
                        str(raw_option.get("explanation")).strip()
                        if raw_option.get("explanation") is not None
                        else None
                    ),
                )
            )
        return options, option_id_map

    def _parse_bool(self, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False
        return False

    def _parse_answer_key(
        self,
        *,
        expected_question_type: ExamQuestionType,
        raw_answer_key: object,
        option_id_map: dict[str, str],
    ) -> ExamQuestionAnswerKey | None:
        if not isinstance(raw_answer_key, dict):
            return None
        has_subjective_fields = any(
            key in raw_answer_key
            for key in (
                "model_answer",
                "acceptable_answers",
                "required_keywords",
            )
        )
        has_oral_fields = any(
            key in raw_answer_key
            for key in ("expected_points", "follow_up_questions")
        )
        if (
            expected_question_type is ExamQuestionType.SUBJECTIVE
            and has_oral_fields
        ) or (
            expected_question_type is ExamQuestionType.ORAL
            and has_subjective_fields
        ):
            raise ExamQuestionGenerationFailedException()
        if expected_question_type is ExamQuestionType.MULTIPLE_CHOICE:
            correct_option_ids = [
                option_id_map.get(option_id, option_id)
                for option_id in self._normalize_text_list(
                    raw_answer_key.get("correct_option_ids")
                )
            ]
            return ExamQuestionAnswerKey(
                type=ExamQuestionType.MULTIPLE_CHOICE,
                correct_option_ids=correct_option_ids,
            )
        if expected_question_type is ExamQuestionType.SUBJECTIVE:
            model_answer = raw_answer_key.get("model_answer")
            if model_answer is None or not str(model_answer).strip():
                raise ExamQuestionGenerationFailedException()
            return ExamQuestionAnswerKey(
                type=ExamQuestionType.SUBJECTIVE,
                model_answer=str(model_answer).strip(),
                acceptable_answers=self._normalize_text_list(
                    raw_answer_key.get("acceptable_answers")
                ),
                required_keywords=self._normalize_text_list(
                    raw_answer_key.get("required_keywords")
                ),
            )
        return ExamQuestionAnswerKey(
            type=ExamQuestionType.ORAL,
            expected_points=self._normalize_text_list(
                raw_answer_key.get("expected_points")
            ),
            follow_up_questions=self._normalize_text_list(
                raw_answer_key.get("follow_up_questions")
            ),
        )

    def _parse_rubric(self, raw_rubric: object) -> ExamQuestionRubric:
        if not isinstance(raw_rubric, dict):
            return ExamQuestionRubric()
        raw_criteria = raw_rubric.get("criteria")
        criteria = []
        if isinstance(raw_criteria, list):
            for raw_criterion in raw_criteria:
                if not isinstance(raw_criterion, dict):
                    continue
                name = str(raw_criterion.get("name") or "").strip()
                description = str(
                    raw_criterion.get("description") or ""
                ).strip()
                points = self._parse_rubric_points(raw_criterion.get("points"))
                if not name or not description:
                    raise ExamQuestionGenerationFailedException()
                criteria.append(
                    ExamQuestionRubricCriterion(
                        name=name,
                        description=description,
                        points=points,
                    )
                )
        evidence_policy = raw_rubric.get("evidence_policy")
        return ExamQuestionRubric(
            criteria=criteria,
            evidence_policy=(
                str(evidence_policy).strip()
                if evidence_policy is not None and str(evidence_policy).strip()
                else None
            ),
        )

    def _parse_rubric_points(self, value: object) -> float:
        try:
            points = float(value)
        except (TypeError, ValueError):
            raise ExamQuestionGenerationFailedException() from None
        if not math.isfinite(points) or points <= 0:
            raise ExamQuestionGenerationFailedException()
        return points

    def _normalize_text_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _normalize_source_material_ids(
        self,
        *,
        item: dict,
        allowed_material_ids: dict[str, UUID],
    ) -> list[UUID]:
        normalized = []
        raw_ids = item.get("source_material_ids", [])
        if isinstance(raw_ids, list):
            for raw_id in raw_ids:
                material_id = allowed_material_ids.get(str(raw_id).strip())
                if material_id is not None and material_id not in normalized:
                    normalized.append(material_id)

        if normalized or not allowed_material_ids:
            return normalized
        return list(allowed_material_ids.values())

    def _validate_duplicate_question_texts(
        self,
        drafts: list[GeneratedExamQuestionDraft],
    ) -> None:
        seen_texts: set[str] = set()
        for draft in drafts:
            normalized_text = " ".join(draft.question_text.lower().split())
            if normalized_text in seen_texts:
                raise ExamQuestionGenerationFailedException()
            seen_texts.add(normalized_text)

    def _validate_bloom_distribution(
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

    def _validate_question_type_distribution(
        self,
        *,
        drafts: list[GeneratedExamQuestionDraft],
        distribution: dict[ExamQuestionType, int],
    ) -> None:
        actual_distribution: dict[ExamQuestionType, int] = {}
        for draft in drafts:
            actual_distribution[draft.question_type] = (
                actual_distribution.get(draft.question_type, 0) + 1
            )
        for question_type, expected_count in distribution.items():
            if actual_distribution.get(question_type, 0) != expected_count:
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
