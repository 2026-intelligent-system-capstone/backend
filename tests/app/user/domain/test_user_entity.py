from uuid import uuid4

from app.user.domain.entity.user import Profile, User, UserRole, UserStatus


def test_user_entity_creation_with_profile():
    profile = Profile(
        nickname="tester",
        name="김테스트",
        phone_number="010-1234-5678",
    )

    user = User(
        organization_id=uuid4(),
        login_id="20260001",
        role=UserRole.STUDENT,
        email="test@example.com",
        profile=profile,
    )

    assert user.login_id == "20260001"
    assert user.profile.name == "김테스트"
    assert user.status == UserStatus.ACTIVE


def test_user_soft_delete():
    user = User(
        organization_id=uuid4(),
        login_id="20260002",
        role=UserRole.STUDENT,
        email=None,
        profile=Profile(nickname="del", name="삭제"),
    )

    user.delete()

    assert user.is_deleted is True
