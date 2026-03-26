from uuid import uuid4

from app.user.domain.entity import User, UserRole, UserStatus


def test_user_entity_creation():
    user = User(
        organization_id=uuid4(),
        login_id="20260001",
        role=UserRole.STUDENT,
        email="test@example.com",
        name="김테스트",
    )

    assert user.login_id == "20260001"
    assert user.name == "김테스트"
    assert user.status == UserStatus.ACTIVE


def test_user_soft_delete():
    user = User(
        organization_id=uuid4(),
        login_id="20260002",
        role=UserRole.STUDENT,
        email=None,
        name="삭제",
    )

    user.delete()

    assert user.is_deleted is True
