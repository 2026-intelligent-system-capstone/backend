from app.user.domain.entity.user import Profile, User, UserStatus


def test_user_entity_creation_with_profile():
    # Given
    profile = Profile(nickname="tester", real_name="김테스트", phone_number="010-1234-5678")

    # When
    user = User(username="testuser", password="hashed_password", email="test@example.com", profile=profile)

    # Then
    assert user.username == "testuser"
    assert user.profile.real_name == "김테스트"
    assert user.status == UserStatus.ACTIVE
    assert user.oauth_provider is None


def test_user_oauth_support():
    # Given
    profile = Profile(nickname="social_user", real_name="이사회")

    # When
    user = User(
        username="kakao_12345",
        password=None,
        email="social@example.com",
        profile=profile,
        oauth_provider="kakao",
        oauth_id="12345",
    )

    # Then
    assert user.password is None
    assert user.oauth_provider == "kakao"
    assert user.oauth_id == "12345"


def test_user_soft_delete():
    # Given
    profile = Profile(nickname="del", real_name="삭제")
    user = User(username="del_user", password="p", email="d@e.com", profile=profile)

    # When
    user.delete()

    # Then
    assert user.is_deleted is True
