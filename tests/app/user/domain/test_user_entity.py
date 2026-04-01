from uuid import uuid4

from app.user.domain.entity import User, UserRole, UserStatus


def test_user_entity_creation():
    user = User.register(
        organization_id=uuid4(),
        login_id="20260001",
        role=UserRole.STUDENT,
        email="test@example.com",
        name="김테스트",
    )

    assert user.login_id == "20260001"
    assert user.name == "김테스트"
    assert user.status == UserStatus.ACTIVE


def test_user_can_login_only_when_not_deleted_or_blocked():
    active_user = User(
        organization_id=uuid4(),
        login_id="20260001",
        role=UserRole.STUDENT,
        email="active@example.com",
        name="활성",
    )
    blocked_user = User(
        organization_id=uuid4(),
        login_id="20260002",
        role=UserRole.STUDENT,
        email="blocked@example.com",
        name="차단",
        status=UserStatus.BLOCKED,
    )
    deleted_user = User(
        organization_id=uuid4(),
        login_id="20260003",
        role=UserRole.STUDENT,
        email="deleted@example.com",
        name="삭제",
    )
    deleted_user.delete()

    assert active_user.can_login is True
    assert blocked_user.can_login is False
    assert deleted_user.can_login is False


def test_user_update_supports_partial_changes_and_explicit_email_clear():
    user = User(
        organization_id=uuid4(),
        login_id="20260002",
        role=UserRole.STUDENT,
        email="before@example.com",
        name="변경 전",
    )

    user.update(
        login_id="20260099",
        role=UserRole.PROFESSOR,
        clear_email=True,
        name="변경 후",
        status=UserStatus.BLOCKED,
    )

    assert user.login_id == "20260099"
    assert user.role == UserRole.PROFESSOR
    assert user.name == "변경 후"
    assert user.status == UserStatus.BLOCKED
    assert user.email is None


def test_user_sync_profile_updates_all_profile_fields():
    user = User(
        organization_id=uuid4(),
        login_id="20260002",
        role=UserRole.STUDENT,
        email="before@example.com",
        name="이전 이름",
    )

    user.sync_profile(
        login_id="20260123",
        role=UserRole.ADMIN,
        email="after@example.com",
        name="새 이름",
    )

    assert user.login_id == "20260123"
    assert user.role == UserRole.ADMIN
    assert user.email == "after@example.com"
    assert user.name == "새 이름"


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
