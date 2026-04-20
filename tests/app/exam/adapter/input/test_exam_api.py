from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.async_job.domain.entity import AsyncJobReference, AsyncJobStatus, AsyncJobTargetType, AsyncJobType
from app.exam.application.exception import (
    ExamNotFoundException,
    ExamQuestionGenerationAlreadyInProgressException,
    ExamQuestionGenerationMaterialIngestFailedException,
    ExamQuestionGenerationMaterialNotFoundException,
    ExamQuestionGenerationMaterialNotReadyException,
    ExamSessionAlreadyInProgressException,
    ExamSessionMaxAttemptsExceededException,
    ExamSessionUnavailableException,
)
from app.exam.application.service import ExamService
from app.exam.domain.entity import (
    BloomLevel,
    Exam,
    ExamCriterion,
    ExamDifficulty,
    ExamGenerationStatus,
    ExamQuestion,
    ExamQuestionStatus,
    ExamQuestionType,
    ExamQuestionTypeStrategy,
    ExamResultCriterion,
    ExamStatus,
    ExamType,
)
from app.exam.domain.service import ExamQuestionGenerationSubmitResult
from app.user.adapter.output.persistence.sqlalchemy import (
    UserSQLAlchemyRepository,
)
from app.user.domain.entity import User, UserRole
from core.config import config
from core.domain.types import TokenType
from core.helpers.token import TokenHelper
from main import create_app

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")
EXAM_ID = UUID("33333333-3333-3333-3333-333333333333")
PROFESSOR_ID = UUID("44444444-4444-4444-4444-444444444444")
STUDENT_ID = UUID("55555555-5555-5555-5555-555555555555")
STARTS_AT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
ENDS_AT = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
WEEK = 1


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def make_exam(*, max_attempts: int = 1) -> Exam:
    exam = Exam(
        classroom_id=CLASSROOM_ID,
        title="중간 평가",
        description="1주차 범위 평가",
        exam_type=ExamType.MIDTERM,
        status=ExamStatus.READY,
        duration_minutes=60,
        starts_at=STARTS_AT,
        ends_at=ENDS_AT,
        max_attempts=max_attempts,
        week=WEEK,
        criteria=[
            ExamCriterion(
                exam_id=EXAM_ID,
                title="개념 이해",
                description="핵심 개념을 설명하는지 평가",
                weight=100,
                sort_order=1,
                excellent_definition="핵심 개념을 정확히 설명한다.",
                average_definition=("핵심 개념 설명은 가능하나 연결이 약하다."),
                poor_definition="핵심 개념 이해가 부족하다.",
            )
        ],
    )
    exam.id = EXAM_ID
    return exam


def make_question(
    *,
    question_number: int = 1,
    max_score: float = 1.0,
    question_type: ExamQuestionType = ExamQuestionType.SUBJECTIVE,
    question_text: str = "회귀와 분류의 차이를 설명하세요.",
    rubric_text: str = "출력 형태와 문제 목적 차이를 포함하고 핵심 개념과 예시를 설명하면 정답",
    answer_options: list[str] | None = None,
    correct_answer_text: str | None = "회귀와 분류",
    status: ExamQuestionStatus = ExamQuestionStatus.GENERATED,
):
    question = ExamQuestion(
        exam_id=EXAM_ID,
        question_number=question_number,
        max_score=max_score,
        question_type=question_type,
        bloom_level=BloomLevel.APPLY,
        difficulty=ExamDifficulty.MEDIUM,
        question_text=question_text,
        intent_text="1주차 머신러닝 기초 범위에서 지도학습 구분 능력 평가",
        rubric_text=rubric_text,
        answer_options=list(answer_options or []),
        correct_answer_text=correct_answer_text,
        source_material_ids=[
            UUID("99999999-9999-9999-9999-999999999999")
        ],
        status=status,
    )
    question.id = UUID("88888888-8888-8888-8888-888888888888")
    return question


def make_user(*, role: UserRole, user_id: UUID) -> User:
    user = User(
        organization_id=ORG_ID,
        login_id="user01",
        role=role,
        email="user@example.com",
        name="사용자",
    )
    user.id = user_id
    return user


def set_access_token_cookie(client: TestClient, user: User) -> None:
    access_token = TokenHelper.create_token(
        payload={"sub": str(user.id)},
        token_type=TokenType.ACCESS,
    )
    client.cookies.set(config.ACCESS_TOKEN_COOKIE_NAME, access_token)


def test_create_exam_returns_200_for_professor(client, monkeypatch):
    captured = {}

    async def create_stub_exam(*_args, **kwargs):
        captured["command"] = kwargs["command"]
        return make_exam()

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(ExamService, "create_exam", create_stub_exam)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams",
        json={
            "title": "중간 평가",
            "description": "1주차 범위 평가",
            "exam_type": "midterm",
            "duration_minutes": 60,
            "starts_at": STARTS_AT.isoformat(),
            "ends_at": ENDS_AT.isoformat(),
            "max_attempts": 1,
            "week": WEEK,
            "criteria": [
                {
                    "title": "개념 이해",
                    "description": "핵심 개념을 설명하는지 평가",
                    "weight": 100,
                    "sort_order": 1,
                    "excellent_definition": "핵심 개념을 정확히 설명한다.",
                    "average_definition": (
                        "핵심 개념 설명은 가능하나 연결이 약하다."
                    ),
                    "poor_definition": "핵심 개념 이해가 부족하다.",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert captured["command"].week == WEEK
    assert captured["command"].max_attempts == 1
    assert response.json()["data"]["title"] == "중간 평가"
    assert response.json()["data"]["exam_type"] == "midterm"
    assert response.json()["data"]["status"] == "ready"
    assert response.json()["data"]["week"] == WEEK
    assert response.json()["data"]["criteria"][0]["title"] == "개념 이해"


def test_create_exam_accepts_weekly_and_project_types(client, monkeypatch):
    captured_commands = []

    async def create_stub_exam(*_args, **kwargs):
        command = kwargs["command"]
        captured_commands.append(command)
        exam = make_exam()
        exam.title = command.title
        exam.exam_type = command.exam_type
        return exam

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(ExamService, "create_exam", create_stub_exam)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    weekly_response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams",
        json={
            "title": "주간 평가",
            "description": "주차 확인 평가",
            "exam_type": "weekly",
            "duration_minutes": 30,
            "starts_at": STARTS_AT.isoformat(),
            "ends_at": ENDS_AT.isoformat(),
            "max_attempts": 1,
            "week": WEEK,
            "criteria": [
                {
                    "title": "개념 이해",
                    "description": "핵심 개념을 설명하는지 평가",
                    "weight": 100,
                    "sort_order": 1,
                    "excellent_definition": "핵심 개념을 정확히 설명한다.",
                    "average_definition": "핵심 개념 설명은 가능하나 연결이 약하다.",
                    "poor_definition": "핵심 개념 이해가 부족하다.",
                }
            ],
        },
    )

    project_response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams",
        json={
            "title": "프로젝트 평가",
            "description": "프로젝트 결과물 평가",
            "exam_type": "project",
            "duration_minutes": 90,
            "starts_at": STARTS_AT.isoformat(),
            "ends_at": ENDS_AT.isoformat(),
            "max_attempts": 1,
            "week": WEEK,
            "criteria": [
                {
                    "title": "설계 근거",
                    "description": "구현 의사결정의 근거를 설명하는지 평가",
                    "weight": 100,
                    "sort_order": 1,
                    "excellent_definition": "설계 선택과 근거를 논리적으로 설명한다.",
                    "average_definition": "선택은 설명하지만 근거 연결이 약하다.",
                    "poor_definition": "설계 근거 설명이 부족하다.",
                }
            ],
        },
    )

    assert weekly_response.status_code == 200
    assert weekly_response.json()["data"]["exam_type"] == "weekly"
    assert project_response.status_code == 200
    assert project_response.json()["data"]["exam_type"] == "project"
    assert [command.exam_type for command in captured_commands] == [
        ExamType.WEEKLY,
        ExamType.PROJECT,
    ]


def test_list_exams_returns_200_for_student(client, monkeypatch):
    async def list_stub_exams(*_args, **_kwargs):
        exam = make_exam()
        exam.generation_status = ExamGenerationStatus.QUEUED
        exam.generation_job_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        exam.generation_requested_at = STARTS_AT
        exam.add_question(
            question_number=1,
            max_score=2.5,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="회귀와 분류의 차이를 설명하세요.",
            intent_text="1주차 머신러닝 기초 범위에서 지도학습 구분 능력 평가",
            rubric_text="출력 형태와 문제 목적 차이를 포함하고 핵심 개념과 예시를 설명하면 정답",
            source_material_ids=[
                UUID("99999999-9999-9999-9999-999999999999")
            ],
        )
        deleted_question = exam.add_question(
            question_number=2,
            max_score=1.0,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="삭제된 문항",
            intent_text="1주차 머신러닝 기초 범위의 삭제 테스트 문항",
            rubric_text="삭제 응답에서 제외되어야 하는 문항",
            source_material_ids=[
                UUID("99999999-9999-9999-9999-999999999999")
            ],
        )
        deleted_question.delete()
        return [exam]

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "list_exams", list_stub_exams)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(f"/api/classrooms/{CLASSROOM_ID}/exams")

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["id"] == str(EXAM_ID)
    assert response.json()["data"][0]["week"] == WEEK
    assert response.json()["data"][0]["duration_minutes"] == 60
    assert response.json()["data"][0]["criteria"][0]["weight"] == 100
    assert response.json()["data"][0]["generation_status"] == "queued"
    assert response.json()["data"][0]["generation_job_id"] == (
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )
    assert response.json()["data"][0]["generation_requested_at"] == STARTS_AT.isoformat()
    assert len(response.json()["data"][0]["questions"]) == 1
    assert response.json()["data"][0]["questions"][0]["question_number"] == 1
    assert response.json()["data"][0]["questions"][0]["max_score"] == 2.5
    assert response.json()["data"][0]["questions"][0]["rubric_text"] == ""
    assert response.json()["data"][0]["questions"][0]["answer_options"] == []
    assert response.json()["data"][0]["questions"][0]["correct_answer_text"] is None


def test_get_exam_returns_200(client, monkeypatch):
    async def get_stub_exam(*_args, **_kwargs):
        exam = make_exam()
        exam.generation_status = ExamGenerationStatus.FAILED
        exam.generation_error = "생성 중 오류가 발생했습니다."
        exam.generation_job_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        exam.generation_requested_at = STARTS_AT
        exam.generation_completed_at = ENDS_AT
        exam.add_question(
            question_number=1,
            max_score=2.5,
            question_type=ExamQuestionType.SUBJECTIVE,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="회귀와 분류의 차이를 설명하세요.",
            intent_text="1주차 머신러닝 기초 범위에서 지도학습 구분 능력 평가",
            rubric_text="출력 형태와 문제 목적 차이를 포함하고 핵심 개념과 예시를 설명하면 정답",
            correct_answer_text="출력 변수 예측은 회귀, 범주 예측은 분류",
            source_material_ids=[
                UUID("99999999-9999-9999-9999-999999999999")
            ],
        )
        exam.add_question(
            question_number=2,
            max_score=3.0,
            question_type=ExamQuestionType.MULTIPLE_CHOICE,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="지도학습에 해당하는 것을 고르세요.",
            intent_text="지도학습 개념을 구분하는지 평가",
            rubric_text="정답 선택 근거를 설명하고 오답과 구분하면 우수",
            answer_options=[
                "클러스터링",
                "차원 축소",
                "회귀",
                "연관 규칙",
                "주성분 분석",
            ],
            correct_answer_text="회귀",
            source_material_ids=[
                UUID("99999999-9999-9999-9999-999999999999")
            ],
        )
        exam.add_question(
            question_number=3,
            max_score=4.0,
            question_type=ExamQuestionType.ORAL,
            bloom_level=BloomLevel.ANALYZE,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="모델 성능 저하 원인을 말로 설명하세요.",
            intent_text="성능 저하 원인을 분석적으로 설명하는지 평가",
            rubric_text="과적합, 데이터 편향, 피처 품질 저하를 언급하면 우수",
            source_material_ids=[
                UUID("99999999-9999-9999-9999-999999999999")
            ],
        )
        deleted_question = exam.add_question(
            question_number=4,
            max_score=1.0,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="삭제된 문항",
            intent_text="1주차 머신러닝 기초 범위의 삭제 테스트 문항",
            rubric_text="삭제 응답에서 제외되어야 하는 문항",
            source_material_ids=[
                UUID("99999999-9999-9999-9999-999999999999")
            ],
        )
        deleted_question.delete()
        return exam

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(ExamService, "get_exam", get_stub_exam)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.get(f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(EXAM_ID)
    assert response.json()["data"]["description"] == "1주차 범위 평가"
    assert response.json()["data"]["week"] == WEEK
    assert response.json()["data"]["max_attempts"] == 1
    assert response.json()["data"]["generation_status"] == "failed"
    assert response.json()["data"]["generation_error"] == "생성 중 오류가 발생했습니다."
    assert response.json()["data"]["generation_job_id"] == (
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    )
    assert response.json()["data"]["generation_requested_at"] == STARTS_AT.isoformat()
    assert response.json()["data"]["generation_completed_at"] == ENDS_AT.isoformat()
    assert response.json()["data"]["criteria"][0]["excellent_definition"] == (
        "핵심 개념을 정확히 설명한다."
    )
    questions = response.json()["data"]["questions"]

    assert len(questions) == 3
    assert questions[0]["question_number"] == 1
    assert questions[0]["max_score"] == 2.5
    assert questions[0]["intent_text"] == "1주차 머신러닝 기초 범위에서 지도학습 구분 능력 평가"
    assert questions[0]["rubric_text"] == "출력 형태와 문제 목적 차이를 포함하고 핵심 개념과 예시를 설명하면 정답"
    assert questions[0]["correct_answer_text"] == "출력 변수 예측은 회귀, 범주 예측은 분류"
    assert questions[0]["answer_options"] == []
    assert questions[1]["question_type"] == "multiple_choice"
    assert questions[1]["max_score"] == 3.0
    assert questions[1]["answer_options"] == [
        "클러스터링",
        "차원 축소",
        "회귀",
        "연관 규칙",
        "주성분 분석",
    ]
    assert questions[1]["correct_answer_text"] == "회귀"
    assert questions[2]["question_type"] == "oral"
    assert questions[2]["max_score"] == 4.0
    assert questions[2]["answer_options"] == []
    assert questions[2]["correct_answer_text"] is None


def test_create_exam_returns_422_for_invalid_week(client, monkeypatch):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams",
        json={
            "title": "중간 평가",
            "description": "1주차 범위 평가",
            "exam_type": "midterm",
            "duration_minutes": 60,
            "starts_at": STARTS_AT.isoformat(),
            "ends_at": ENDS_AT.isoformat(),
            "max_attempts": 1,
            "week": 0,
            "criteria": [
                {
                    "title": "개념 이해",
                    "description": "핵심 개념을 설명하는지 평가",
                    "weight": 100,
                    "sort_order": 1,
                    "excellent_definition": "핵심 개념을 정확히 설명한다.",
                    "average_definition": (
                        "핵심 개념 설명은 가능하나 연결이 약하다."
                    ),
                    "poor_definition": "핵심 개념 이해가 부족하다.",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_list_exams_hides_answers_for_student(client, monkeypatch):
    async def list_stub_exams(*_args, **_kwargs):
        exam = make_exam()
        exam.add_question(
            question_number=1,
            max_score=2.5,
            question_type=ExamQuestionType.SUBJECTIVE,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="회귀와 분류의 차이를 설명하세요.",
            intent_text="1주차 머신러닝 기초 범위에서 지도학습 구분 능력 평가",
            rubric_text="출력 형태와 문제 목적 차이를 포함하고 핵심 개념과 예시를 설명하면 정답",
            source_material_ids=[
                UUID("99999999-9999-9999-9999-999999999999")
            ],
        )
        return [exam]

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "list_exams", list_stub_exams)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(f"/api/classrooms/{CLASSROOM_ID}/exams")

    assert response.status_code == 200
    assert response.json()["data"][0]["questions"][0]["max_score"] == 2.5
    assert response.json()["data"][0]["questions"][0]["rubric_text"] == ""
    assert response.json()["data"][0]["questions"][0]["answer_options"] == []
    assert response.json()["data"][0]["questions"][0]["correct_answer_text"] is None


def test_get_exam_hides_answers_for_student(client, monkeypatch):
    async def get_stub_exam(*_args, **_kwargs):
        exam = make_exam()
        exam.add_question(
            question_number=1,
            max_score=2.5,
            question_type=ExamQuestionType.SUBJECTIVE,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="회귀와 분류의 차이를 설명하세요.",
            intent_text="1주차 머신러닝 기초 범위에서 지도학습 구분 능력 평가",
            rubric_text="출력 형태와 문제 목적 차이를 포함하고 핵심 개념과 예시를 설명하면 정답",
            source_material_ids=[
                UUID("99999999-9999-9999-9999-999999999999")
            ],
        )
        return exam

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "get_exam", get_stub_exam)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}")

    assert response.status_code == 200
    assert response.json()["data"]["questions"][0]["max_score"] == 2.5
    assert response.json()["data"]["questions"][0]["rubric_text"] == ""
    assert response.json()["data"]["questions"][0]["answer_options"] == []
    assert response.json()["data"]["questions"][0]["correct_answer_text"] is None


def test_create_exam_question_returns_200_for_professor(client, monkeypatch):
    async def create_question_stub(*_args, **_kwargs):
        return make_question(max_score=2.5)

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ExamService,
        "create_exam_question",
        create_question_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions",
        json={
            "question_number": 1,
            "max_score": 2.5,
            "question_type": "subjective",
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "회귀와 분류의 차이를 설명하세요.",
            "intent_text": "1주차 머신러닝 기초 범위에서 지도학습 구분 능력 평가",
            "rubric_text": "출력 형태와 문제 목적 차이를 포함하고 핵심 개념과 예시를 설명하면 정답",
            "correct_answer_text": "회귀와 분류",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["question_type"] == "subjective"
    assert response.json()["data"]["bloom_level"] == "apply"
    assert response.json()["data"]["difficulty"] == "medium"
    assert response.json()["data"]["max_score"] == 2.5
    assert response.json()["data"]["answer_options"] == []
    assert response.json()["data"]["correct_answer_text"] == "회귀와 분류"
    assert response.json()["data"]["source_material_ids"] == [
        "99999999-9999-9999-9999-999999999999"
    ]


def test_create_exam_question_returns_422_when_subjective_correct_answer_missing(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions",
        json={
            "question_number": 1,
            "max_score": 1.0,
            "question_type": "subjective",
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "회귀와 분류의 차이를 설명하세요.",
            "intent_text": "주관식에서 핵심 개념 구분 능력을 평가합니다.",
            "rubric_text": "핵심 개념과 예시를 설명하면 정답",
            "source_material_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_create_exam_question_returns_422_when_oral_rubric_missing(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions",
        json={
            "question_number": 1,
            "max_score": 1.0,
            "question_type": "oral",
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "회귀와 분류의 차이를 설명하세요.",
            "intent_text": "구술형에서 개념 구분 능력을 평가합니다.",
            "source_material_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_create_exam_question_returns_422_when_multiple_choice_answer_options_missing(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions",
        json={
            "question_number": 1,
            "max_score": 1.0,
            "question_type": "multiple_choice",
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "지도학습 예시를 고르세요.",
            "intent_text": "객관식에서 개념 분류 능력을 평가합니다.",
            "rubric_text": "정확한 개념 선택 여부를 평가합니다.",
            "correct_answer_text": "회귀",
            "source_material_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_create_exam_question_returns_422_when_multiple_choice_has_single_answer_option(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions",
        json={
            "question_number": 1,
            "max_score": 1.0,
            "question_type": "multiple_choice",
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "지도학습 예시를 고르세요.",
            "intent_text": "객관식에서 개념 분류 능력을 평가합니다.",
            "rubric_text": "정확한 개념 선택 여부를 평가합니다.",
            "answer_options": ["회귀"],
            "correct_answer_text": "회귀",
            "source_material_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_create_exam_question_returns_422_when_multiple_choice_correct_answer_missing(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions",
        json={
            "question_number": 1,
            "max_score": 1.0,
            "question_type": "multiple_choice",
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "지도학습 예시를 고르세요.",
            "intent_text": "객관식에서 개념 분류 능력을 평가합니다.",
            "rubric_text": "정확한 개념 선택 여부를 평가합니다.",
            "answer_options": ["회귀", "분류", "강화학습"],
            "source_material_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_create_exam_question_returns_422_when_multiple_choice_correct_answer_not_in_options(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions",
        json={
            "question_number": 1,
            "max_score": 1.0,
            "question_type": "multiple_choice",
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "지도학습 예시를 고르세요.",
            "intent_text": "객관식에서 개념 분류 능력을 평가합니다.",
            "rubric_text": "정확한 개념 선택 여부를 평가합니다.",
            "answer_options": ["회귀", "분류", "강화학습"],
            "correct_answer_text": "군집화",
            "source_material_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_update_exam_question_returns_200_for_professor(client, monkeypatch):
    async def update_question_stub(*_args, **_kwargs):
        question = make_question(max_score=2.5)
        question.question_text = "수정된 질문"
        question.status = ExamQuestionStatus.REVIEWED
        return question

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ExamService,
        "update_exam_question",
        update_question_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/"
        "88888888-8888-8888-8888-888888888888",
        json={"question_text": "수정된 질문", "max_score": 2.5},
    )

    assert response.status_code == 200
    assert response.json()["data"]["question_text"] == "수정된 질문"
    assert response.json()["data"]["question_type"] == "subjective"
    assert response.json()["data"]["max_score"] == 2.5
    assert response.json()["data"]["answer_options"] == []
    assert response.json()["data"]["correct_answer_text"] == "회귀와 분류"
    assert response.json()["data"]["status"] == "reviewed"


def test_update_exam_question_returns_422_when_switching_to_oral_without_rubric(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/"
        "88888888-8888-8888-8888-888888888888",
        json={"question_type": "oral"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_update_exam_question_returns_422_when_switching_to_subjective_without_correct_answer(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/"
        "88888888-8888-8888-8888-888888888888",
        json={"question_type": "subjective"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_update_exam_question_returns_422_when_switching_to_multiple_choice_without_answer_options(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/"
        "88888888-8888-8888-8888-888888888888",
        json={
            "question_type": "multiple_choice",
            "correct_answer_text": "회귀",
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_update_exam_question_returns_422_when_switching_to_multiple_choice_without_correct_answer(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/"
        "88888888-8888-8888-8888-888888888888",
        json={
            "question_type": "multiple_choice",
            "answer_options": ["회귀", "분류"],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_create_exam_question_returns_422_for_non_positive_max_score(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions",
        json={
            "question_number": 1,
            "max_score": 0,
            "question_type": "subjective",
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "회귀와 분류의 차이를 설명하세요.",
            "intent_text": "1주차 머신러닝 기초 범위에서 지도학습 구분 능력 평가",
            "rubric_text": "출력 형태와 문제 목적 차이를 포함하고 핵심 개념과 예시를 설명하면 정답",
            "correct_answer_text": "회귀와 분류",
            "source_material_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_update_exam_question_returns_422_for_non_positive_max_score(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/"
        "88888888-8888-8888-8888-888888888888",
        json={"max_score": 0},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_delete_exam_question_returns_200_for_professor(client, monkeypatch):
    async def delete_question_stub(*_args, **_kwargs):
        question = make_question()
        question.status = ExamQuestionStatus.DELETED
        return question

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ExamService,
        "delete_exam_question",
        delete_question_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.delete(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/"
        "88888888-8888-8888-8888-888888888888"
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "deleted"
    assert response.json()["data"]["max_score"] == 1.0
    assert response.json()["data"]["answer_options"] == []
    assert response.json()["data"]["correct_answer_text"] == "회귀와 분류"


def test_create_exam_question_returns_403_for_student(client, monkeypatch):
    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions",
        json={
            "question_number": 1,
            "max_score": 1.0,
            "question_type": "subjective",
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "회귀와 분류의 차이를 설명하세요.",
            "intent_text": "1주차 머신러닝 기초 범위에서 지도학습 구분 능력 평가",
            "rubric_text": "출력 형태와 문제 목적 차이를 포함하고 핵심 개념과 예시를 설명하면 정답",
            "source_material_ids": [],
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_generate_exam_questions_returns_202_for_professor(
    client,
    monkeypatch,
):
    captured = {}

    async def generate_questions_stub(*_args, **kwargs):
        captured.update(kwargs)
        return ExamQuestionGenerationSubmitResult(
            exam_id=EXAM_ID,
            generation_status=ExamGenerationStatus.QUEUED,
            job=AsyncJobReference(
                job_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                job_type=AsyncJobType.EXAM_QUESTION_GENERATION,
                status=AsyncJobStatus.QUEUED,
                target_type=AsyncJobTargetType.EXAM,
                target_id=EXAM_ID,
            ),
            generation_requested_at=STARTS_AT,
            generation_error=None,
        )

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ExamService,
        "generate_exam_questions",
        generate_questions_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "bloom_counts": [
                {"bloom_level": "apply", "count": 1}
            ],
            "question_type_counts": [
                {"question_type": "subjective", "count": 1}
            ],
        },
    )

    body = response.json()

    assert response.status_code == 202
    assert captured["classroom_id"] == CLASSROOM_ID
    assert captured["exam_id"] == EXAM_ID
    assert captured["command"].scope_text == "1주차 머신러닝 기초"
    assert captured["command"].max_follow_ups == 2
    assert captured["command"].difficulty is ExamDifficulty.MEDIUM
    assert captured["command"].source_material_ids == [
        UUID("99999999-9999-9999-9999-999999999999")
    ]
    assert captured["command"].question_type_counts[0].question_type is (
        ExamQuestionType.SUBJECTIVE
    )
    assert captured["command"].question_type_counts[0].count == 1
    assert captured["command"].total_question_count is None
    assert captured["command"].question_type_strategy is None
    assert body["data"]["exam_id"] == str(EXAM_ID)
    assert body["data"]["generation_status"] == "queued"
    assert body["data"]["job_id"] == (
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )
    assert body["data"]["job_status"] == "queued"
    assert body["data"]["generation_requested_at"] == STARTS_AT.isoformat()
    assert body["data"]["generation_error"] is None


def test_generate_exam_questions_returns_202_for_strategy_request(
    client,
    monkeypatch,
):
    captured = {}

    async def generate_questions_stub(*_args, **kwargs):
        captured.update(kwargs)
        return ExamQuestionGenerationSubmitResult(
            exam_id=EXAM_ID,
            generation_status=ExamGenerationStatus.QUEUED,
            job=AsyncJobReference(
                job_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                job_type=AsyncJobType.EXAM_QUESTION_GENERATION,
                status=AsyncJobStatus.QUEUED,
                target_type=AsyncJobTargetType.EXAM,
                target_id=EXAM_ID,
            ),
            generation_requested_at=STARTS_AT,
            generation_error=None,
        )

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ExamService,
        "generate_exam_questions",
        generate_questions_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "total_question_count": 3,
            "question_type_strategy": "oral_focus",
            "bloom_counts": [
                {"bloom_level": "remember", "count": 1},
                {"bloom_level": "apply", "count": 2}
            ],
        },
    )

    assert response.status_code == 202
    assert captured["command"].total_question_count == 3
    assert captured["command"].question_type_strategy is ExamQuestionTypeStrategy.ORAL_FOCUS
    assert captured["command"].question_type_counts is None
    assert [item.count for item in captured["command"].bloom_counts] == [1, 2]



def test_generate_exam_questions_returns_400_for_invalid_materials(
    client,
    monkeypatch,
):
    async def generate_questions_stub(*_args, **_kwargs):
        raise ExamQuestionGenerationMaterialNotFoundException()

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ExamService,
        "generate_exam_questions",
        generate_questions_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "bloom_counts": [
                {"bloom_level": "apply", "count": 1}
            ],
            "question_type_counts": [
                {"question_type": "subjective", "count": 1}
            ],
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == (
        "EXAM_QUESTION_GENERATION__INVALID_SOURCE_MATERIALS"
    )


def test_generate_exam_questions_returns_400_for_pending_material(
    client,
    monkeypatch,
):
    async def generate_questions_stub(*_args, **_kwargs):
        raise ExamQuestionGenerationMaterialNotReadyException()

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ExamService,
        "generate_exam_questions",
        generate_questions_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "bloom_counts": [
                {"bloom_level": "apply", "count": 1}
            ],
            "question_type_counts": [
                {"question_type": "subjective", "count": 1}
            ],
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == (
        "EXAM_QUESTION_GENERATION__SOURCE_MATERIALS_NOT_READY"
    )


def test_generate_exam_questions_returns_409_for_already_in_progress(
    client,
    monkeypatch,
):
    async def generate_questions_stub(*_args, **_kwargs):
        raise ExamQuestionGenerationAlreadyInProgressException()

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ExamService,
        "generate_exam_questions",
        generate_questions_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "bloom_counts": [
                {"bloom_level": "apply", "count": 1}
            ],
            "question_type_counts": [
                {"question_type": "subjective", "count": 1}
            ],
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == (
        "EXAM_QUESTION_GENERATION__ALREADY_IN_PROGRESS"
    )



def test_generate_exam_questions_returns_400_for_failed_material(
    client,
    monkeypatch,
):
    async def generate_questions_stub(*_args, **_kwargs):
        raise ExamQuestionGenerationMaterialIngestFailedException()

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ExamService,
        "generate_exam_questions",
        generate_questions_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "bloom_counts": [
                {"bloom_level": "apply", "count": 1}
            ],
            "question_type_counts": [
                {"question_type": "subjective", "count": 1}
            ],
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == (
        "EXAM_QUESTION_GENERATION__SOURCE_MATERIALS_INGEST_FAILED"
    )


def test_generate_exam_questions_returns_422_for_legacy_mismatched_totals(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "bloom_counts": [
                {"bloom_level": "apply", "count": 1}
            ],
            "question_type_counts": [
                {"question_type": "subjective", "count": 2}
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"



def test_generate_exam_questions_returns_422_for_strategy_total_mismatch(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "total_question_count": 2,
            "question_type_strategy": "oral_focus",
            "bloom_counts": [
                {"bloom_level": "apply", "count": 3}
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"



def test_generate_exam_questions_returns_422_for_mixed_strategy_and_legacy_mode(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "total_question_count": 1,
            "question_type_strategy": "oral_focus",
            "bloom_counts": [
                {"bloom_level": "apply", "count": 1}
            ],
            "question_type_counts": [
                {"question_type": "subjective", "count": 1}
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_generate_exam_questions_returns_422_for_invalid_question_type(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "bloom_counts": [
                {"bloom_level": "apply", "count": 1}
            ],
            "question_type_counts": [
                {"question_type": "essay", "count": 1}
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_generate_exam_questions_returns_422_for_none_question_type(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "bloom_counts": [
                {"bloom_level": "apply", "count": 1}
            ],
            "question_type_counts": [
                {"question_type": "none", "count": 1}
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_generate_exam_questions_accepts_question_type_count_above_five(
    client,
    monkeypatch,
):
    captured = {}

    async def generate_questions_stub(*_args, **kwargs):
        captured.update(kwargs)
        return ExamQuestionGenerationSubmitResult(
            exam_id=EXAM_ID,
            generation_status=ExamGenerationStatus.QUEUED,
            job=AsyncJobReference(
                job_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                job_type=AsyncJobType.EXAM_QUESTION_GENERATION,
                status=AsyncJobStatus.QUEUED,
                target_type=AsyncJobTargetType.EXAM,
                target_id=EXAM_ID,
            ),
            generation_requested_at=STARTS_AT,
            generation_error=None,
        )

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ExamService,
        "generate_exam_questions",
        generate_questions_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/questions/generate",
        json={
            "scope_text": "1주차 머신러닝 기초",
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "bloom_counts": [
                {"bloom_level": "remember", "count": 5},
                {"bloom_level": "understand", "count": 5},
                {"bloom_level": "apply", "count": 2}
            ],
            "question_type_counts": [
                {"question_type": "subjective", "count": 6},
                {"question_type": "oral", "count": 6}
            ],
        },
    )

    assert response.status_code == 202
    assert captured["command"].question_type_counts[0].count == 6
    assert captured["command"].question_type_counts[1].count == 6


def test_list_student_exams_returns_200_for_student(client, monkeypatch):
    async def list_student_exams_stub(*_args, **_kwargs):
        exam = make_exam()
        exam.questions = [
            make_question(
                question_type=ExamQuestionType.MULTIPLE_CHOICE,
                answer_options=["회귀", "분류"],
                correct_answer_text="분류",
            )
        ]
        return [
            SimpleNamespace(
                exam=exam,
                is_completed=True,
                can_enter=False,
                latest_result=None,
            )
        ]

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(
        ExamService,
        "list_student_exams",
        list_student_exams_stub,
        raising=False,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get("/api/exams")

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["id"] == str(EXAM_ID)
    assert response.json()["data"][0]["title"] == "중간 평가"
    assert response.json()["data"][0]["status"] == "ready"
    assert response.json()["data"][0]["week"] == WEEK
    assert response.json()["data"][0]["is_completed"] is True
    assert response.json()["data"][0]["can_enter"] is False
    assert response.json()["data"][0]["latest_result"] is None
    assert response.json()["data"][0]["questions"][0]["question_text"] == ""
    assert response.json()["data"][0]["questions"][0]["rubric_text"] == ""
    assert response.json()["data"][0]["questions"][0]["answer_options"] == []
    assert (
        response.json()["data"][0]["questions"][0]["correct_answer_text"]
        is None
    )


def test_get_student_exam_returns_200_for_student(client, monkeypatch):
    async def get_student_exam_stub(*_args, **_kwargs):
        exam = make_exam()
        exam.questions = [
            make_question(
                question_type=ExamQuestionType.MULTIPLE_CHOICE,
                answer_options=["회귀", "분류"],
                correct_answer_text="분류",
            )
        ]
        return SimpleNamespace(
            exam=exam,
            is_completed=True,
            can_enter=False,
            latest_result=None,
        )

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(
        ExamService,
        "get_student_exam",
        get_student_exam_stub,
        raising=False,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(f"/api/exams/{EXAM_ID}")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(EXAM_ID)
    assert response.json()["data"]["title"] == "중간 평가"
    assert response.json()["data"]["status"] == "ready"
    assert response.json()["data"]["week"] == WEEK
    assert response.json()["data"]["is_completed"] is True
    assert response.json()["data"]["can_enter"] is False
    assert response.json()["data"]["latest_result"] is None
    assert response.json()["data"]["questions"][0]["question_text"] == ""
    assert response.json()["data"]["questions"][0]["rubric_text"] == ""
    assert response.json()["data"]["questions"][0]["answer_options"] == []
    assert response.json()["data"]["questions"][0]["correct_answer_text"] is None


def test_start_exam_session_returns_200_for_student(client, monkeypatch):
    async def start_session_stub(*_args, **_kwargs):
        class Session:
            id = UUID("66666666-6666-6666-6666-666666666666")
            exam_id = EXAM_ID
            student_id = STUDENT_ID
            status = type("Status", (), {"value": "in_progress"})()
            started_at = STARTS_AT
            expires_at = ENDS_AT

        class Result:
            session = Session()
            client_secret = "secret-value"

        return Result()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "start_exam_session", start_session_stub)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(f"/api/exams/{EXAM_ID}/sessions")

    assert response.status_code == 200
    assert response.json()["data"]["exam_id"] == str(EXAM_ID)
    assert response.json()["data"]["student_id"] == str(STUDENT_ID)
    assert response.json()["data"]["status"] == "in_progress"
    assert response.json()["data"]["client_secret"] == "secret-value"


def test_get_student_exam_returns_404_when_exam_not_found(client, monkeypatch):
    async def get_student_exam_stub(*_args, **_kwargs):
        raise ExamNotFoundException()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(
        ExamService,
        "get_student_exam",
        get_student_exam_stub,
        raising=False,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(f"/api/exams/{EXAM_ID}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "EXAM__NOT_FOUND"


def test_start_exam_session_returns_409_when_session_unavailable(client, monkeypatch):
    async def start_session_stub(*_args, **_kwargs):
        raise ExamSessionUnavailableException()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "start_exam_session", start_session_stub)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(f"/api/exams/{EXAM_ID}/sessions")

    assert response.status_code == 409
    assert response.json()["error_code"] == "EXAM_SESSION__UNAVAILABLE"


def test_start_exam_session_returns_409_when_session_already_in_progress(
    client, monkeypatch
):
    async def start_session_stub(*_args, **_kwargs):
        raise ExamSessionAlreadyInProgressException()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "start_exam_session", start_session_stub)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(f"/api/exams/{EXAM_ID}/sessions")

    assert response.status_code == 409
    assert response.json()["error_code"] == "EXAM_SESSION__ALREADY_IN_PROGRESS"


def test_start_exam_session_returns_409_when_max_attempts_exceeded(
    client, monkeypatch
):
    async def start_session_stub(*_args, **_kwargs):
        raise ExamSessionMaxAttemptsExceededException()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "start_exam_session", start_session_stub)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(f"/api/exams/{EXAM_ID}/sessions")

    assert response.status_code == 409
    assert response.json()["error_code"] == "EXAM_SESSION__MAX_ATTEMPTS_EXCEEDED"


def test_list_my_exam_results_returns_200_for_student(client, monkeypatch):
    async def list_results_stub(*_args, **_kwargs):
        class Result:
            id = UUID("77777777-7777-7777-7777-777777777777")
            exam_id = EXAM_ID
            session_id = UUID("66666666-6666-6666-6666-666666666666")
            student_id = STUDENT_ID
            status = type("Status", (), {"value": "completed"})()
            submitted_at = ENDS_AT
            overall_score = 87.5
            summary = "핵심 개념은 이해했지만 적용 예시 설명은 더 필요합니다."
            strengths = ["지도학습 정의를 정확히 설명했습니다."]
            weaknesses = ["대표 알고리즘 예시가 부족했습니다."]
            improvement_suggestions = ["분류와 회귀 예시를 함께 연습하세요."]
            criteria_results = [
                ExamResultCriterion(
                    criterion_id=UUID("99999999-9999-9999-9999-999999999998"),
                    score=87.5,
                    feedback="핵심 개념 설명은 정확하지만 적용 예시가 다소 부족합니다.",
                )
            ]

        return [Result()]

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "list_my_exam_results", list_results_stub)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(f"/api/exams/{EXAM_ID}/results/me")

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["student_id"] == str(STUDENT_ID)
    assert response.json()["data"][0]["status"] == "completed"
    assert response.json()["data"][0]["overall_score"] == 87.5
    assert response.json()["data"][0]["strengths"] == ["지도학습 정의를 정확히 설명했습니다."]
    assert response.json()["data"][0]["weaknesses"] == ["대표 알고리즘 예시가 부족했습니다."]
    assert response.json()["data"][0]["improvement_suggestions"] == ["분류와 회귀 예시를 함께 연습하세요."]
    assert response.json()["data"][0]["criteria_results"] == [
        {
            "criterion_id": "99999999-9999-9999-9999-999999999998",
            "score": 87.5,
            "feedback": "핵심 개념 설명은 정확하지만 적용 예시가 다소 부족합니다.",
        }
    ]


def test_record_exam_turn_returns_200_for_student(client, monkeypatch):
    async def record_turn_stub(*_args, **_kwargs):
        class Turn:
            id = UUID("88888888-8888-8888-8888-888888888888")
            session_id = UUID("66666666-6666-6666-6666-666666666666")
            sequence = 1
            role = type("Role", (), {"value": "assistant"})()
            event_type = type("EventType", (), {"value": "question"})()
            content = "머신러닝과 딥러닝의 차이를 설명해보세요."
            created_at = STARTS_AT
            metadata = {"message_id": "msg-question-1"}

        return Turn()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "record_exam_turn", record_turn_stub)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(
        f"/api/exams/{EXAM_ID}/sessions/"
        "66666666-6666-6666-6666-666666666666/turns",
        json={
            "role": "assistant",
            "event_type": "question",
            "content": "머신러닝과 딥러닝의 차이를 설명해보세요.",
            "metadata": {"message_id": "msg-question-1"},
            "occurred_at": STARTS_AT.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["sequence"] == 1
    assert response.json()["data"]["role"] == "assistant"
    assert response.json()["data"]["event_type"] == "question"


def test_complete_exam_session_returns_200_for_student(client, monkeypatch):
    async def complete_session_stub(*_args, **_kwargs):
        class Session:
            id = UUID("66666666-6666-6666-6666-666666666666")
            exam_id = EXAM_ID
            student_id = STUDENT_ID
            status = type("Status", (), {"value": "completed"})()
            started_at = STARTS_AT
            expires_at = ENDS_AT
            ended_at = ENDS_AT

        return Session()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(
        ExamService, "complete_exam_session", complete_session_stub
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(
        f"/api/exams/{EXAM_ID}/sessions/"
        "66666666-6666-6666-6666-666666666666/complete",
        json={"occurred_at": ENDS_AT.isoformat()},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"


def test_finalize_exam_result_returns_200_for_student(client, monkeypatch):
    captured_command: dict[str, object] = {}

    async def finalize_result_stub(*_args, **kwargs):
        captured_command["command"] = kwargs["command"]

        class Result:
            id = UUID("77777777-7777-7777-7777-777777777777")
            exam_id = EXAM_ID
            session_id = UUID("66666666-6666-6666-6666-666666666666")
            student_id = STUDENT_ID
            status = type("Status", (), {"value": "pending"})()
            submitted_at = None
            overall_score = None
            summary = None

        return Result()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(
        ExamService, "finalize_exam_result", finalize_result_stub
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(
        f"/api/exams/{EXAM_ID}/sessions/"
        "66666666-6666-6666-6666-666666666666/results/finalize",
        json={
            "occurred_at": ENDS_AT.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "pending"
    assert response.json()["data"]["overall_score"] is None
    assert captured_command["command"].occurred_at == ENDS_AT


def test_finalize_exam_result_rejects_client_score_fields(client, monkeypatch):
    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(
        f"/api/exams/{EXAM_ID}/sessions/"
        "66666666-6666-6666-6666-666666666666/results/finalize",
        json={
            "overall_score": 92,
            "summary": "개념 이해와 문제 해결 과정이 모두 우수합니다.",
            "occurred_at": ENDS_AT.isoformat(),
        },
    )

    assert response.status_code == 422
