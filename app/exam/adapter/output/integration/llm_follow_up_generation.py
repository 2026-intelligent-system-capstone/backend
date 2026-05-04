from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

from openai import AsyncOpenAI

from app.exam.application.exception import (
    ExamQuestionGenerationUnavailableException,
)
from app.exam.domain.entity import ExamTurnEventType
from app.exam.domain.service import (
    ExamFollowUpGenerationPort,
    ExamFollowUpGenerationRequest,
    ExamFollowUpGenerationResult,
    ExamFollowUpGenerationTurn,
)
from core.config import config

NO_FOLLOW_UP_CONTENT = (
    "후속 질문이 필요하지 않습니다. 다음 문항으로 이동합니다."
)

FOLLOW_UP_EVALUATOR_SYSTEM_PROMPT = """
당신은 학생과 직접 소통하며 구술 시험 답변을 평가하는 AI 면접관입니다.
학생의 최근 답변과 같은 문항의 대화 이력만 근거로
후속 질문 필요 여부를 판단합니다.
반드시 JSON만 응답합니다.

{
  "needs_follow_up": true,
  "reason": "...",
  "request_to_generator": "..."
}
""".strip()

FOLLOW_UP_GENERATOR_SYSTEM_PROMPT = """
당신은 학생의 이해 척도를 평가하기 위한 문제를 제작하는 AI 문항 생성자입니다.
요청 사항과 원 문항 정보를 바탕으로 학생에게 바로 제시할
후속 질문 하나만 생성합니다.
반드시 JSON만 응답합니다.

{
  "follow_up_question": "..."
}
""".strip()


class LLMExamFollowUpGenerationAdapter(ExamFollowUpGenerationPort):
    async def generate_follow_up(
        self,
        *,
        request: ExamFollowUpGenerationRequest,
    ) -> ExamFollowUpGenerationResult:
        if not config.OPENAI_API_KEY:
            raise ExamQuestionGenerationUnavailableException(
                message=(
                    "OPENAI_API_KEY가 설정되지 않아 "
                    "후속 질문을 생성할 수 없습니다."
                )
            )

        openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        evaluator_response = await self._create_completion(
            openai_client=openai_client,
            messages=[
                {
                    "role": "system",
                    "content": FOLLOW_UP_EVALUATOR_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": self._build_evaluator_prompt(request=request),
                },
            ],
        )
        evaluator = self._parse_json(self._extract_content(evaluator_response))
        needs_follow_up = self._extract_needs_follow_up(evaluator)
        reason = str(evaluator.get("reason") or "")
        follow_up_count = self._count_follow_ups(request)
        metadata = {
            "needs_follow_up": str(needs_follow_up).lower(),
            "reason": reason,
            "follow_up_count": str(follow_up_count),
            "max_follow_ups": str(request.question.max_follow_ups),
        }

        max_follow_ups = request.question.max_follow_ups
        if (not needs_follow_up) or follow_up_count >= max_follow_ups:
            return ExamFollowUpGenerationResult(
                content=NO_FOLLOW_UP_CONTENT,
                event_type=ExamTurnEventType.MESSAGE,
                metadata=metadata,
            )

        generator_response = await self._create_completion(
            openai_client=openai_client,
            messages=[
                {
                    "role": "system",
                    "content": FOLLOW_UP_GENERATOR_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": self._build_generator_prompt(
                        request=request,
                        request_to_generator=str(
                            evaluator.get("request_to_generator") or ""
                        ),
                    ),
                },
            ],
        )
        generator = self._parse_json(self._extract_content(generator_response))
        follow_up_question = str(
            generator.get("follow_up_question") or ""
        ).strip()
        if not follow_up_question:
            raise ExamQuestionGenerationUnavailableException(
                message="AI가 유효한 후속 질문을 생성하지 못했습니다."
            )
        return ExamFollowUpGenerationResult(
            content=follow_up_question,
            event_type=ExamTurnEventType.FOLLOW_UP,
            metadata=metadata,
        )

    async def _create_completion(
        self,
        *,
        openai_client: AsyncOpenAI,
        messages: list[dict[str, str]],
    ) -> Any:
        try:
            return await openai_client.chat.completions.create(
                model=config.OPENAI_EXAM_GENERATION_MODEL,
                response_format={"type": "json_object"},
                messages=messages,
            )
        except Exception as exc:
            raise ExamQuestionGenerationUnavailableException(
                message="AI 후속 질문 생성 요청에 실패했습니다."
            ) from exc

    def _extract_content(self, response: Any) -> str:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise ExamQuestionGenerationUnavailableException(
                message="AI 후속 질문 생성 응답이 올바르지 않습니다."
            ) from exc
        return content or "{}"

    def _extract_needs_follow_up(self, evaluator: dict[str, object]) -> bool:
        needs_follow_up = evaluator.get("needs_follow_up")
        if not isinstance(needs_follow_up, bool):
            raise ExamQuestionGenerationUnavailableException(
                message="AI 후속 질문 평가 응답이 올바르지 않습니다."
            )
        return needs_follow_up

    def _build_evaluator_prompt(
        self, *, request: ExamFollowUpGenerationRequest
    ) -> str:
        return (
            f"## 시험 정보\n"
            f"- exam_id: {request.exam_id}\n"
            f"- session_id: {request.session_id}\n"
            f"- student_id: {request.student_id}\n"
            f"- exam_title: {request.exam_title}\n\n"
            f"## 원 문항\n"
            f"- question_id: {request.question.question_id}\n"
            f"- question_number: {request.question.question_number}\n"
            f"- question_type: {request.question.question_type.value}\n"
            f"- bloom_level: {request.question.bloom_level.value}\n"
            f"- difficulty: {request.question.difficulty.value}\n"
            f"- question_text: {request.question.question_text}\n"
            f"- intent_text: {request.question.intent_text}\n"
            f"- rubric_text: {request.question.rubric_text}\n"
            f"- max_follow_ups: {request.question.max_follow_ups}\n\n"
            f"## 최근 답변\n{request.answer_content}\n\n"
            "## 같은 문항 대화 이력\n"
            f"{self._build_same_question_history(request)}"
        )

    def _build_generator_prompt(
        self,
        *,
        request: ExamFollowUpGenerationRequest,
        request_to_generator: str,
    ) -> str:
        source_material_ids = ", ".join(
            str(material_id)
            for material_id in request.question.source_material_ids
        )
        return (
            f"## 생성 요청\n{request_to_generator}\n\n"
            f"## 원 문항\n"
            f"- question_id: {request.question.question_id}\n"
            f"- question_text: {request.question.question_text}\n"
            f"- intent_text: {request.question.intent_text}\n"
            f"- rubric_text: {request.question.rubric_text}\n"
            f"- source_material_ids: {source_material_ids or '-'}\n\n"
            f"## 학생 답변\n{request.answer_content}\n\n"
            f"학생의 이해를 더 정확히 확인할 후속 질문 하나를 생성하세요."
        )

    def _build_same_question_history(
        self, request: ExamFollowUpGenerationRequest
    ) -> str:
        turns = [
            turn
            for turn in request.turns
            if self._matches_question(turn, request)
        ]
        if not turns:
            return "- 대화 이력 없음"

        return "\n".join(self._format_turn(turn) for turn in turns)

    def _format_turn(self, turn: ExamFollowUpGenerationTurn) -> str:
        return (
            f"- sequence: {turn.sequence}\n"
            f"  role: {turn.role.value}\n"
            f"  event_type: {turn.event_type.value}\n"
            f"  content: {turn.content}"
        )

    def _matches_question(
        self,
        turn: ExamFollowUpGenerationTurn,
        request: ExamFollowUpGenerationRequest,
    ) -> bool:
        return turn.metadata.get("question_id") == str(
            request.question.question_id
        )

    def _count_follow_ups(self, request: ExamFollowUpGenerationRequest) -> int:
        return sum(
            1
            for turn in request.turns
            if self._matches_question(turn, request)
            and turn.event_type is ExamTurnEventType.FOLLOW_UP
        )

    def _parse_json(self, content: str) -> dict[str, object]:
        try:
            parsed = json.loads(content)
        except JSONDecodeError as exc:
            raise ExamQuestionGenerationUnavailableException(
                message="AI 후속 질문 생성 응답이 JSON 형식이 아닙니다."
            ) from exc
        if not isinstance(parsed, dict):
            raise ExamQuestionGenerationUnavailableException(
                message="AI 후속 질문 생성 응답이 올바르지 않습니다."
            )
        return parsed
