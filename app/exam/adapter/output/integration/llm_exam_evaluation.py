from __future__ import annotations

import json
from json import JSONDecodeError
from uuid import UUID

from openai import AsyncOpenAI

from app.exam.domain.service import (
    EvaluateExamResult,
    EvaluateExamResultRequest,
    ExamResultEvaluationCriterionScore,
    ExamResultEvaluationPort,
)
from core.config import config

EXAM_RESULT_EVALUATION_SYSTEM_PROMPT = """
당신은 대학 구술형 평가 결과를 루브릭 기준으로 채점하는 평가자입니다.

## 평가 원칙
1. 반드시 제공된 평가 기준(criteria)만 근거로 채점합니다.
2. 학생의 답변(turns)에 없는 내용을 추정하지 않습니다.
3. 각 criterion score는 0점 이상 100점 이하 실수여야 합니다.
4. feedback은 criterion별 강점/보완점을 간결하게 설명합니다.
5. summary, strengths, weaknesses, improvement_suggestions는 모두
   한국어로 작성합니다.
6. 반드시 JSON만 응답합니다.

## 출력 형식
{
  "summary": "...",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "improvement_suggestions": ["..."],
  "criteria_results": [
    {
      "criterion_id": "uuid",
      "score": 0,
      "feedback": "..."
    }
  ]
}
""".strip()


class LLMExamResultEvaluationAdapter(ExamResultEvaluationPort):
    async def evaluate_result(
        self,
        *,
        request: EvaluateExamResultRequest,
    ) -> EvaluateExamResult:
        if not config.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY가 설정되지 않아 자동 평가를 수행할 수 없습니다."
            )

        openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        completion = await openai_client.chat.completions.create(
            model=config.OPENAI_EXAM_GENERATION_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": EXAM_RESULT_EVALUATION_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": self._build_user_prompt(request=request),
                },
            ],
        )
        content = completion.choices[0].message.content or "{}"
        return self._parse_response(content=content, request=request)

    def _build_user_prompt(self, *, request: EvaluateExamResultRequest) -> str:
        criteria_text = "\n".join(
            (
                f"- id: {criterion.criterion_id}\n"
                f"  title: {criterion.title}\n"
                f"  weight: {criterion.weight}\n"
                f"  description: {criterion.description or '-'}\n"
                "  excellent_definition: "
                f"{criterion.excellent_definition or '-'}\n"
                f"  average_definition: {criterion.average_definition or '-'}\n"
                f"  poor_definition: {criterion.poor_definition or '-'}"
            )
            for criterion in request.criteria
        )
        questions_text = "\n".join(
            (
                f"- question_number: {question.question_number}\n"
                f"  question_type: {question.question_type.value}\n"
                f"  difficulty: {question.difficulty.value}\n"
                f"  question_text: {question.question_text}\n"
                f"  intent_text: {question.intent_text}\n"
                f"  rubric_text: {question.rubric_text}"
            )
            for question in request.questions
        )
        turns_text = "\n".join(
            (
                f"- sequence: {turn.sequence}\n"
                f"  role: {turn.role.value}\n"
                f"  event_type: {turn.event_type.value}\n"
                f"  content: {turn.content}"
            )
            for turn in request.turns
        )
        return (
            f"## 시험 정보\n"
            f"- exam_id: {request.exam_id}\n"
            f"- session_id: {request.session_id}\n"
            f"- student_id: {request.student_id}\n"
            f"- exam_title: {request.exam_title}\n"
            f"- exam_type: {request.exam_type.value}\n\n"
            f"## 평가 기준\n"
            f"{criteria_text or '- 기준 없음'}\n\n"
            f"## 문항\n"
            f"{questions_text or '- 문항 없음'}\n\n"
            f"## 시험 대화 기록\n"
            f"{turns_text or '- 대화 없음'}\n\n"
            "위 정보를 바탕으로 criterion별 점수와 피드백, 전체 요약, "
            "강점, 약점, 개선 제안을 생성하세요."
        )

    def _parse_response(
        self,
        *,
        content: str,
        request: EvaluateExamResultRequest,
    ) -> EvaluateExamResult:
        try:
            parsed = json.loads(self._strip_code_block(content))
        except JSONDecodeError as exc:
            raise RuntimeError(
                "자동 평가 응답을 JSON으로 해석하지 못했습니다."
            ) from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("자동 평가 응답 형식이 올바르지 않습니다.")

        raw_summary = str(parsed.get("summary") or "").strip()
        if not raw_summary:
            raise RuntimeError("자동 평가 요약이 비어 있습니다.")

        allowed_criterion_ids = {
            criterion.criterion_id for criterion in request.criteria
        }
        raw_results = parsed.get("criteria_results", [])
        if not isinstance(raw_results, list):
            raise RuntimeError(
                "자동 평가 criterion 결과 형식이 올바르지 않습니다."
            )

        criteria_results: list[ExamResultEvaluationCriterionScore] = []
        seen_criterion_ids: set[UUID] = set()
        for item in raw_results:
            if not isinstance(item, dict):
                raise RuntimeError(
                    "자동 평가 criterion 결과 형식이 올바르지 않습니다."
                )
            try:
                criterion_id = UUID(str(item.get("criterion_id") or "").strip())
                score = float(item.get("score"))
                feedback = str(item.get("feedback") or "").strip()
            except (ValueError, TypeError) as exc:
                raise RuntimeError(
                    "자동 평가 criterion 결과 값이 올바르지 않습니다."
                ) from exc
            if criterion_id not in allowed_criterion_ids:
                raise RuntimeError(
                    "자동 평가 criterion_id가 시험 기준과 일치하지 않습니다."
                )
            if criterion_id in seen_criterion_ids:
                raise RuntimeError(
                    "자동 평가 criterion 결과에 중복 criterion_id가 "
                    "포함되었습니다."
                )
            if score < 0 or score > 100:
                raise RuntimeError("자동 평가 score는 0~100 범위여야 합니다.")
            if not feedback:
                raise RuntimeError(
                    "자동 평가 criterion feedback이 비어 있습니다."
                )
            seen_criterion_ids.add(criterion_id)
            criteria_results.append(
                ExamResultEvaluationCriterionScore(
                    criterion_id=criterion_id,
                    score=score,
                    feedback=feedback,
                )
            )

        if seen_criterion_ids != allowed_criterion_ids:
            raise RuntimeError(
                "자동 평가 criterion 결과가 시험 기준과 일치하지 않습니다."
            )

        return EvaluateExamResult(
            summary=raw_summary,
            strengths=self._parse_string_list(parsed.get("strengths")),
            weaknesses=self._parse_string_list(parsed.get("weaknesses")),
            improvement_suggestions=self._parse_string_list(
                parsed.get("improvement_suggestions")
            ),
            criteria_results=criteria_results,
        )

    def _parse_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _strip_code_block(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```json"):
            return stripped.removeprefix("```json").removesuffix("```").strip()
        if stripped.startswith("```"):
            return stripped.removeprefix("```").removesuffix("```").strip()
        return stripped
