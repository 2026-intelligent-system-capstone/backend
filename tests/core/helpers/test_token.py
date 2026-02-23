import pytest
from core.helpers.token import TokenHelper
from core.config import config

def test_create_and_decode_access_token():
    # Given
    payload = {"user_id": 1, "role": "admin"}
    
    # When
    token = TokenHelper.create_access_token(payload=payload)
    decoded = TokenHelper.decode_token(token)
    
    # Then
    assert decoded["user_id"] == 1
    assert decoded["role"] == "admin"
    assert "exp" in decoded

def test_create_and_decode_refresh_token():
    # Given
    payload = {"user_id": 1}
    
    # When
    token = TokenHelper.create_refresh_token(payload=payload)
    decoded = TokenHelper.decode_token(token)
    
    # Then
    assert decoded["user_id"] == 1
    assert "exp" in decoded

def test_decode_invalid_token():
    # Given
    invalid_token = "invalid.token.here"
    
    # When & Then
    with pytest.raises(Exception): # JWT error
        TokenHelper.decode_token(invalid_token)

def test_expired_token():
    # Given
    payload = {"user_id": 1}
    # Create a token that expires in -1 second
    token = TokenHelper._create_token(payload=payload, expires_delta=-1)
    
    # When & Then
    with pytest.raises(Exception): # ExpiredSignatureError
        TokenHelper.decode_token(token)
