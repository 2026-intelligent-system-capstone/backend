from uuid import UUID

from app.exam.adapter.output.integration.llm_exam_evaluation import (
    LLMExamResultEvaluationAdapter,
)
from app.exam.domain.entity import (
    ExamDifficulty,
    ExamQuestionAnswerKey,
    ExamQuestionRubric,
    ExamQuestionRubricCriterion,
    ExamQuestionType,
    ExamTurnEventType,
    ExamTurnRole,
    ExamType,
)
from app.exam.domain.service import (
    EvaluateExamResultRequest,
    ExamResultEvaluationQuestion,
    ExamResultEvaluationTurn,
)

EXAM_ID = UUID("11111111-1111-1111-1111-111111111111")
SESSION_ID = UUID("22222222-2222-2222-2222-222222222222")
STUDENT_ID = UUID("33333333-3333-3333-3333-333333333333")


def test_build_user_prompt_includes_structured_subjective_and_oral_data():
    adapter = LLMExamResultEvaluationAdapter()
    request = EvaluateExamResultRequest(
        exam_id=EXAM_ID,
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        exam_title="중간 평가",
        exam_type=ExamType.MIDTERM,
        questions=[
            ExamResultEvaluationQuestion(
                question_id=UUID("44444444-4444-4444-4444-444444444444"),
                question_number=1,
                max_score=5.0,
                question_type=ExamQuestionType.SUBJECTIVE,
                difficulty=ExamDifficulty.MEDIUM,
                question_text="지도학습을 설명하세요.",
                intent_text="개념 이해를 평가합니다.",
                rubric_text="핵심 키워드를 포함합니다.",
                answer_key_data=ExamQuestionAnswerKey(
                    type=ExamQuestionType.SUBJECTIVE,
                    model_answer="레이블 데이터로 학습하는 방법",
                    acceptable_answers=["정답 데이터 기반 학습"],
                    required_keywords=["레이블", "학습"],
                ),
                rubric_data=ExamQuestionRubric(
                    criteria=[
                        ExamQuestionRubricCriterion(
                            name="핵심 키워드",
                            description="레이블과 학습을 언급한다.",
                            points=3.0,
                        )
                    ],
                    evidence_policy="학생 답변에 있는 근거만 사용합니다.",
                ),
            ),
            ExamResultEvaluationQuestion(
                question_id=UUID("55555555-5555-5555-5555-555555555555"),
                question_number=2,
                max_score=5.0,
                question_type=ExamQuestionType.ORAL,
                difficulty=ExamDifficulty.MEDIUM,
                question_text="적용 사례를 설명하세요.",
                intent_text="적용 설명 능력을 평가합니다.",
                rubric_text="근거와 예시를 포함합니다.",
                answer_key_data=ExamQuestionAnswerKey(
                    type=ExamQuestionType.ORAL,
                    expected_points=["적용 사례", "근거"],
                    follow_up_questions=["한계를 추가로 설명해보세요."],
                ),
                rubric_data=ExamQuestionRubric(
                    criteria=[
                        ExamQuestionRubricCriterion(
                            name="구술 설명",
                            description="근거와 예시를 제시한다.",
                            points=2.0,
                        )
                    ],
                ),
            ),
        ],
        turns=[
            ExamResultEvaluationTurn(
                sequence=1,
                role=ExamTurnRole.STUDENT,
                event_type=ExamTurnEventType.ANSWER,
                content="학생 답변",
                metadata={"question_number": "1"},
            )
        ],
    )

    prompt = adapter._build_user_prompt(request=request)

    assert "model_answer: 레이블 데이터로 학습하는 방법" in prompt
    assert "acceptable_answers: 정답 데이터 기반 학습" in prompt
    assert "required_keywords: 레이블, 학습" in prompt
    assert "expected_points: 적용 사례, 근거" in prompt
    assert "follow_up_questions: 한계를 추가로 설명해보세요." in prompt
    assert "rubric_criteria:" in prompt
    assert "name: 핵심 키워드" in prompt
    assert "evidence_policy: 학생 답변에 있는 근거만 사용합니다." in prompt


def test_build_user_prompt_exposes_mc_option_id_answer_key():
    adapter = LLMExamResultEvaluationAdapter()
    request = EvaluateExamResultRequest(
        exam_id=EXAM_ID,
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        exam_title="중간 평가",
        exam_type=ExamType.MIDTERM,
        questions=[
            ExamResultEvaluationQuestion(
                question_id=UUID("66666666-6666-6666-6666-666666666666"),
                question_number=1,
                max_score=5.0,
                question_type=ExamQuestionType.MULTIPLE_CHOICE,
                difficulty=ExamDifficulty.MEDIUM,
                question_text="지도학습 설명을 고르세요.",
                intent_text="개념 구분을 평가합니다.",
                rubric_text="정답 선택지를 고르면 만점입니다.",
                answer_key_data=ExamQuestionAnswerKey(
                    type=ExamQuestionType.MULTIPLE_CHOICE,
                    correct_option_ids=["1"],
                ),
                rubric_data=ExamQuestionRubric(),
            )
        ],
    )

    prompt = adapter._build_user_prompt(request=request)

    assert "answer_key_type: multiple_choice" in prompt
    assert "correct_option_ids: 1" in prompt
    assert "correct_answer_text" not in prompt
