from uuid import UUID

import pytest

from app.auth.domain.entity import AuthTokens
from app.auth.domain.exception import AuthInvalidRefreshTokenDomainException
from core.domain.types import TokenType
from core.helpers.token import TokenHelper

USER_ID = UUID("11111111-1111-1111-1111-111111111111")
ORGANIZATION_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_auth_tokens_issue_creates_refresh_claims_and_metadata():
    tokens, refresh_jti = AuthTokens.issue(
        user_id=USER_ID,
        organization_id=ORGANIZATION_ID,
        organization_code="univ_hansung",
        role="student",
    )

    claims = AuthTokens.decode_refresh_token(tokens.refresh_token)
    parsed_user_id, parsed_jti = AuthTokens.parse_refresh_token(
        tokens.refresh_token
    )

    assert tokens.user_id == str(USER_ID)
    assert tokens.organization_id == str(ORGANIZATION_ID)
    assert tokens.organization_code == "univ_hansung"
    assert tokens.role == "student"
    assert claims["sub"] == str(USER_ID)
    assert parsed_user_id == USER_ID
    assert parsed_jti == refresh_jti


def test_auth_tokens_decode_refresh_token_rejects_access_token():
    access_token = TokenHelper.create_token(
        payload={"sub": str(USER_ID)},
        token_type=TokenType.ACCESS,
    )

    with pytest.raises(AuthInvalidRefreshTokenDomainException):
        AuthTokens.decode_refresh_token(access_token)
