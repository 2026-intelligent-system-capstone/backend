import pytest
from jwt import DecodeError

from core.domain.types import TokenType
from core.helpers.token import TokenHelper


def test_create_and_decode_token():
    # Given
    payload = {"user_id": 1}
    token_type = TokenType.ACCESS
    expires_in = 60

    # When
    token = TokenHelper.create_token(
        payload=payload,
        token_type=token_type,
        expires_delta=expires_in,
    )
    decoded = TokenHelper.decode_token(token)

    # Then
    assert decoded["user_id"] == 1
    assert decoded["type"] == TokenType.ACCESS.value
    assert "exp" in decoded


def test_refresh_token_creation_with_minutes():
    # Given
    payload = {"user_id": 1}
    token_type = TokenType.REFRESH
    expires_in = 10080  # 7 days in minutes

    # When
    token = TokenHelper.create_token(
        payload=payload,
        token_type=token_type,
        expires_delta=expires_in,
    )
    decoded = TokenHelper.decode_token(token)

    # Then
    assert decoded["type"] == TokenType.REFRESH.value
    assert "exp" in decoded


def test_decode_invalid_token():
    with pytest.raises(DecodeError):
        TokenHelper.decode_token("invalid.token")
