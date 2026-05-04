import json
from uuid import UUID

import pytest

from app.exam.adapter.output.integration import (
    llm_follow_up_generation as module,
)
from app.exam.adapter.output.integration.llm_follow_up_generation import (
    NO_FOLLOW_UP_CONTENT,
    LLMExamFollowUpGenerationAdapter,
)
from app.exam.application.exception import (
    ExamQuestionGenerationUnavailableException,
)
from app.exam.domain.entity import (
    BloomLevel,
    ExamDifficulty,
    ExamQuestionType,
    ExamTurnEventType,
    ExamTurnRole,
)
from app.exam.domain.service import (
    ExamFollowUpGenerationQuestion,
    ExamFollowUpGenerationRequest,
    ExamFollowUpGenerationTurn,
)

EXAM_ID = UUID("11111111-1111-1111-1111-111111111111")
SESSION_ID = UUID("22222222-2222-2222-2222-222222222222")
STUDENT_ID = UUID("33333333-3333-3333-3333-333333333333")
QUESTION_ID = UUID("44444444-4444-4444-4444-444444444444")
OTHER_QUESTION_ID = UUID("55555555-5555-5555-5555-555555555555")
MATERIAL_ID = UUID("66666666-6666-6666-6666-666666666666")


class FakeChatCompletionsAPI:
    def __init__(self, responses: list[dict[str, object]]):
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if response.get("empty_choices") is True:
            return type("Completion", (), {"choices": []})()
        content = response.get("raw_content")
        if content is None:
            content = json.dumps(response, ensure_ascii=False)
        message = type(
            "Message",
            (),
            {"content": content},
        )()
        choice = type("Choice", (), {"message": message})()
        return type("Completion", (), {"choices": [choice]})()


class FakeAsyncOpenAI:
    responses: list[dict[str, object]] = []
    last_instance = None

    def __init__(self, *, api_key: str):
        self.api_key = api_key
        self.chat = type(
            "ChatAPI",
            (),
            {"completions": FakeChatCompletionsAPI(type(self).responses)},
        )()
        type(self).last_instance = self


def make_request() -> ExamFollowUpGenerationRequest:
    return ExamFollowUpGenerationRequest(
        exam_id=EXAM_ID,
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        exam_title="중간 평가",
        question=ExamFollowUpGenerationQuestion(
            question_id=QUESTION_ID,
            question_number=1,
            question_type=ExamQuestionType.ORAL,
            bloom_level=BloomLevel.UNDERSTAND,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="분류와 회귀의 차이를 설명하세요.",
            intent_text="지도학습 문제 유형 이해를 평가",
            rubric_text="분류와 회귀의 출력 차이를 설명한다.",
            source_material_ids=[MATERIAL_ID],
            max_follow_ups=2,
        ),
        answer_content="분류는 범주, 회귀는 값을 예측합니다.",
        turns=[
            ExamFollowUpGenerationTurn(
                sequence=1,
                role=ExamTurnRole.ASSISTANT,
                event_type=ExamTurnEventType.QUESTION,
                content="분류와 회귀의 차이를 설명하세요.",
                metadata={"question_id": str(QUESTION_ID)},
            ),
            ExamFollowUpGenerationTurn(
                sequence=2,
                role=ExamTurnRole.STUDENT,
                event_type=ExamTurnEventType.ANSWER,
                content="분류는 범주를 예측합니다.",
                metadata={"question_id": str(QUESTION_ID)},
            ),
            ExamFollowUpGenerationTurn(
                sequence=3,
                role=ExamTurnRole.STUDENT,
                event_type=ExamTurnEventType.ANSWER,
                content="다른 질문 답변입니다.",
                metadata={"question_id": str(OTHER_QUESTION_ID)},
            ),
        ],
    )


@pytest.mark.asyncio
async def test_generate_follow_up_skips_generator_when_not_needed(monkeypatch):
    FakeAsyncOpenAI.responses = [
        {
            "needs_follow_up": False,
            "reason": "핵심 개념을 충분히 설명했습니다.",
            "request_to_generator": "",
        }
    ]
    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        module.config, "OPENAI_EXAM_GENERATION_MODEL", "chat-model"
    )

    result = await LLMExamFollowUpGenerationAdapter().generate_follow_up(
        request=make_request()
    )

    assert result.content == NO_FOLLOW_UP_CONTENT
    assert result.event_type is ExamTurnEventType.MESSAGE
    assert result.metadata == {
        "needs_follow_up": "false",
        "reason": "핵심 개념을 충분히 설명했습니다.",
        "follow_up_count": "0",
        "max_follow_ups": "2",
    }
    assert len(FakeAsyncOpenAI.last_instance.chat.completions.calls) == 1


@pytest.mark.asyncio
async def test_generate_follow_up_calls_generator_when_needed(monkeypatch):
    FakeAsyncOpenAI.responses = [
        {
            "needs_follow_up": True,
            "reason": "회귀 설명이 모호합니다.",
            "request_to_generator": "회귀의 출력 형태를 확인하세요.",
        },
        {
            "follow_up_question": (
                "회귀에서 예측하는 값은 어떤 형태인지 설명해 주세요."
            )
        },
    ]
    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        module.config, "OPENAI_EXAM_GENERATION_MODEL", "chat-model"
    )

    result = await LLMExamFollowUpGenerationAdapter().generate_follow_up(
        request=make_request()
    )

    assert result.content == (
        "회귀에서 예측하는 값은 어떤 형태인지 설명해 주세요."
    )
    assert result.event_type is ExamTurnEventType.FOLLOW_UP
    assert result.metadata == {
        "needs_follow_up": "true",
        "reason": "회귀 설명이 모호합니다.",
        "follow_up_count": "0",
        "max_follow_ups": "2",
    }
    completion_calls = FakeAsyncOpenAI.last_instance.chat.completions.calls
    assert len(completion_calls) == 2
    assert completion_calls[0]["messages"][0]["content"].startswith(
        "당신은 학생과 직접 소통하며"
    )
    assert completion_calls[1]["messages"][0]["content"].startswith(
        "당신은 학생의 이해 척도를 평가하기 위한 문제를 제작"
    )
    generator_prompt = completion_calls[1]["messages"][1]["content"]
    assert "회귀의 출력 형태를 확인하세요." in generator_prompt
    assert str(MATERIAL_ID) in completion_calls[1]["messages"][1]["content"]


@pytest.mark.asyncio
async def test_generate_follow_up_skips_generator_when_limit_reached(
    monkeypatch,
):
    FakeAsyncOpenAI.responses = [
        {
            "needs_follow_up": True,
            "reason": "회귀 설명이 모호합니다.",
            "request_to_generator": "회귀의 출력 형태를 확인하세요.",
        },
    ]
    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        module.config, "OPENAI_EXAM_GENERATION_MODEL", "chat-model"
    )
    request = make_request()
    request.turns.append(
        ExamFollowUpGenerationTurn(
            sequence=4,
            role=ExamTurnRole.ASSISTANT,
            event_type=ExamTurnEventType.FOLLOW_UP,
            content="회귀 출력 형태를 더 설명해 주세요.",
            metadata={"question_id": str(QUESTION_ID)},
        )
    )
    request.turns.append(
        ExamFollowUpGenerationTurn(
            sequence=5,
            role=ExamTurnRole.ASSISTANT,
            event_type=ExamTurnEventType.FOLLOW_UP,
            content="연속값 예시를 들어 주세요.",
            metadata={"question_id": str(QUESTION_ID)},
        )
    )

    result = await LLMExamFollowUpGenerationAdapter().generate_follow_up(
        request=request
    )

    assert result.content == NO_FOLLOW_UP_CONTENT
    assert result.event_type is ExamTurnEventType.MESSAGE
    assert result.metadata == {
        "needs_follow_up": "true",
        "reason": "회귀 설명이 모호합니다.",
        "follow_up_count": "2",
        "max_follow_ups": "2",
    }
    assert len(FakeAsyncOpenAI.last_instance.chat.completions.calls) == 1


@pytest.mark.asyncio
async def test_generate_follow_up_history_includes_only_same_question(
    monkeypatch,
):
    FakeAsyncOpenAI.responses = [
        {
            "needs_follow_up": False,
            "reason": "충분합니다.",
            "request_to_generator": "",
        }
    ]
    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        module.config, "OPENAI_EXAM_GENERATION_MODEL", "chat-model"
    )

    await LLMExamFollowUpGenerationAdapter().generate_follow_up(
        request=make_request()
    )

    evaluator_prompt = FakeAsyncOpenAI.last_instance.chat.completions.calls[0][
        "messages"
    ][1]["content"]
    assert "분류는 범주를 예측합니다." in evaluator_prompt
    assert "다른 질문 답변입니다." not in evaluator_prompt


@pytest.mark.asyncio
async def test_generate_follow_up_raises_when_evaluator_returns_invalid_json(
    monkeypatch,
):
    FakeAsyncOpenAI.responses = [{"raw_content": "not-json"}]
    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        module.config, "OPENAI_EXAM_GENERATION_MODEL", "chat-model"
    )

    with pytest.raises(ExamQuestionGenerationUnavailableException):
        await LLMExamFollowUpGenerationAdapter().generate_follow_up(
            request=make_request()
        )


@pytest.mark.asyncio
async def test_generate_follow_up_raises_when_evaluator_needs_flag_is_not_bool(
    monkeypatch,
):
    FakeAsyncOpenAI.responses = [
        {
            "needs_follow_up": "false",
            "reason": "문자열 boolean은 허용하지 않습니다.",
            "request_to_generator": "",
        },
    ]
    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        module.config, "OPENAI_EXAM_GENERATION_MODEL", "chat-model"
    )

    with pytest.raises(ExamQuestionGenerationUnavailableException):
        await LLMExamFollowUpGenerationAdapter().generate_follow_up(
            request=make_request()
        )
    assert len(FakeAsyncOpenAI.last_instance.chat.completions.calls) == 1


@pytest.mark.asyncio
async def test_generate_follow_up_raises_when_generator_returns_empty_question(
    monkeypatch,
):
    FakeAsyncOpenAI.responses = [
        {
            "needs_follow_up": True,
            "reason": "회귀 설명이 모호합니다.",
            "request_to_generator": "회귀의 출력 형태를 확인하세요.",
        },
        {"follow_up_question": "   "},
    ]
    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        module.config, "OPENAI_EXAM_GENERATION_MODEL", "chat-model"
    )

    with pytest.raises(ExamQuestionGenerationUnavailableException):
        await LLMExamFollowUpGenerationAdapter().generate_follow_up(
            request=make_request()
        )


@pytest.mark.asyncio
async def test_generate_follow_up_raises_when_openai_response_has_no_choices(
    monkeypatch,
):
    FakeAsyncOpenAI.responses = [{"empty_choices": True}]
    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        module.config, "OPENAI_EXAM_GENERATION_MODEL", "chat-model"
    )

    with pytest.raises(ExamQuestionGenerationUnavailableException):
        await LLMExamFollowUpGenerationAdapter().generate_follow_up(
            request=make_request()
        )


@pytest.mark.asyncio
async def test_generate_follow_up_raises_when_openai_key_missing(monkeypatch):
    monkeypatch.setattr(module.config, "OPENAI_API_KEY", "")

    with pytest.raises(ExamQuestionGenerationUnavailableException):
        await LLMExamFollowUpGenerationAdapter().generate_follow_up(
            request=make_request()
        )
