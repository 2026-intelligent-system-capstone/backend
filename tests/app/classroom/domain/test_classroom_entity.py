from uuid import UUID

from app.classroom.domain.entity import Classroom

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
PROFESSOR_ID = UUID("22222222-2222-2222-2222-222222222222")
STUDENT_ID = UUID("33333333-3333-3333-3333-333333333333")


def test_classroom_entity_contains_multiple_professors_and_students():
    classroom = Classroom(
        organization_id=ORG_ID,
        name="AI 기초",
        professor_ids=[PROFESSOR_ID],
        grade=3,
        semester="1학기",
        section="01",
        description="AI 입문 강의실",
        student_ids=[STUDENT_ID],
    )

    assert classroom.name == "AI 기초"
    assert classroom.professor_ids == [PROFESSOR_ID]
    assert classroom.student_ids == [STUDENT_ID]
