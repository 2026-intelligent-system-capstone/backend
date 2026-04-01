from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.exam.application.service import ExamService
from app.exam.domain.entity import (
    BloomLevel,
    Exam,
    ExamCriterion,
    ExamDifficulty,
    ExamQuestionStatus,
    ExamStatus,
    ExamType,
)
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


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def make_exam() -> Exam:
    exam = Exam(
        classroom_id=CLASSROOM_ID,
        title="중간 평가",
        description="1주차 범위 평가",
        exam_type=ExamType.MIDTERM,
        status=ExamStatus.READY,
        duration_minutes=60,
        starts_at=STARTS_AT,
        ends_at=ENDS_AT,
        allow_retake=False,
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


def make_question():
    question = type("Question", (), {})()
    question.id = UUID("88888888-8888-8888-8888-888888888888")
    question.exam_id = EXAM_ID
    question.question_number = 1
    question.bloom_level = BloomLevel.APPLY
    question.difficulty = ExamDifficulty.MEDIUM
    question.question_text = "회귀와 분류의 차이를 설명하세요."
    question.scope_text = "1주차 머신러닝 기초"
    question.evaluation_objective = "지도학습 구분 능력 평가"
    question.answer_key = "출력 형태와 문제 목적 차이를 포함해야 함"
    question.scoring_criteria = "핵심 개념과 예시 포함"
    question.source_material_ids = [
        UUID("99999999-9999-9999-9999-999999999999")
    ]
    question.status = ExamQuestionStatus.GENERATED
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
    async def create_stub_exam(*_args, **_kwargs):
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
            "allow_retake": False,
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
    assert response.json()["data"]["title"] == "중간 평가"
    assert response.json()["data"]["exam_type"] == "midterm"
    assert response.json()["data"]["status"] == "ready"
    assert response.json()["data"]["criteria"][0]["title"] == "개념 이해"


def test_list_exams_returns_200_for_student(client, monkeypatch):
    async def list_stub_exams(*_args, **_kwargs):
        return [make_exam()]

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
    assert response.json()["data"][0]["duration_minutes"] == 60
    assert response.json()["data"][0]["criteria"][0]["weight"] == 100


def test_get_exam_returns_200(client, monkeypatch):
    async def get_stub_exam(*_args, **_kwargs):
        return make_exam()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "get_exam", get_stub_exam)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(EXAM_ID)
    assert response.json()["data"]["description"] == "1주차 범위 평가"
    assert response.json()["data"]["allow_retake"] is False
    assert response.json()["data"]["criteria"][0]["excellent_definition"] == (
        "핵심 개념을 정확히 설명한다."
    )


def test_create_exam_question_returns_200_for_professor(client, monkeypatch):
    async def create_question_stub(*_args, **_kwargs):
        return make_question()

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
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "회귀와 분류의 차이를 설명하세요.",
            "scope_text": "1주차 머신러닝 기초",
            "evaluation_objective": "지도학습 구분 능력 평가",
            "answer_key": "출력 형태와 문제 목적 차이를 포함해야 함",
            "scoring_criteria": "핵심 개념과 예시 포함",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["bloom_level"] == "apply"
    assert response.json()["data"]["difficulty"] == "medium"
    assert response.json()["data"]["source_material_ids"] == [
        "99999999-9999-9999-9999-999999999999"
    ]


def test_update_exam_question_returns_200_for_professor(client, monkeypatch):
    async def update_question_stub(*_args, **_kwargs):
        question = make_question()
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
        json={"question_text": "수정된 질문"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["question_text"] == "수정된 질문"
    assert response.json()["data"]["status"] == "reviewed"


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
            "bloom_level": "apply",
            "difficulty": "medium",
            "question_text": "회귀와 분류의 차이를 설명하세요.",
            "scope_text": "1주차 머신러닝 기초",
            "evaluation_objective": "지도학습 구분 능력 평가",
            "answer_key": "출력 형태와 문제 목적 차이를 포함해야 함",
            "scoring_criteria": "핵심 개념과 예시 포함",
            "source_material_ids": [],
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_generate_exam_questions_returns_200_for_professor(
    client,
    monkeypatch,
):
    async def generate_questions_stub(*_args, **_kwargs):
        return [make_question()]

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
            "total_questions": 1,
            "max_follow_ups": 2,
            "difficulty": "medium",
            "source_material_ids": [
                "99999999-9999-9999-9999-999999999999"
            ],
            "bloom_ratios": [
                {"bloom_level": "apply", "percentage": 100}
            ],
        },
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["question_text"] == (
        "회귀와 분류의 차이를 설명하세요."
    )
    assert response.json()["data"][0]["status"] == "generated"


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


def test_list_my_exam_results_returns_200_for_student(client, monkeypatch):
    async def list_results_stub(*_args, **_kwargs):
        class Result:
            id = UUID("77777777-7777-7777-7777-777777777777")
            exam_id = EXAM_ID
            session_id = UUID("66666666-6666-6666-6666-666666666666")
            student_id = STUDENT_ID
            status = type("Status", (), {"value": "pending"})()
            submitted_at = None
            overall_score = None
            summary = None

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
    assert response.json()["data"][0]["status"] == "pending"


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
    async def finalize_result_stub(*_args, **_kwargs):
        class Result:
            id = UUID("77777777-7777-7777-7777-777777777777")
            exam_id = EXAM_ID
            session_id = UUID("66666666-6666-6666-6666-666666666666")
            student_id = STUDENT_ID
            status = type("Status", (), {"value": "completed"})()
            submitted_at = ENDS_AT
            overall_score = 92
            summary = "개념 이해와 문제 해결 과정이 모두 우수합니다."

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
            "overall_score": 92,
            "summary": "개념 이해와 문제 해결 과정이 모두 우수합니다.",
            "occurred_at": ENDS_AT.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"
    assert response.json()["data"]["overall_score"] == 92
