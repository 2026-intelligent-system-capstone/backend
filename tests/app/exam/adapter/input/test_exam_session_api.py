from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.exam.application.service import ExamService
from app.exam.domain.entity import ExamSession, ExamSessionStatus
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
STUDENT_ID = UUID("44444444-4444-4444-4444-444444444444")
SESSION_ID = UUID("55555555-5555-5555-5555-555555555555")
STARTED_AT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
EXPIRES_AT = datetime(2026, 4, 1, 9, 1, tzinfo=UTC)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


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


def test_start_exam_session_returns_200_for_student(client, monkeypatch):
    async def start_stub_session(*_args, **_kwargs):
        session = ExamSession(
            exam_id=EXAM_ID,
            student_id=STUDENT_ID,
            status=ExamSessionStatus.IN_PROGRESS,
            started_at=STARTED_AT,
            last_activity_at=STARTED_AT,
            expires_at=EXPIRES_AT,
            attempt_number=1,
            provider_session_id="sess_test_123",
        )
        session.id = SESSION_ID
        return type(
            "StartedExamSession",
            (),
            {"session": session, "client_secret": "ek_test_secret"},
        )()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(ExamService, "start_exam_session", start_stub_session)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/exams/{EXAM_ID}/sessions"
    )

    assert response.status_code == 200
    assert response.json()["data"]["session_id"] == str(SESSION_ID)
    assert response.json()["data"]["status"] == "in_progress"
    assert response.json()["data"]["client_secret"] == "ek_test_secret"
