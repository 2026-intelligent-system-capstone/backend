import pytest
from argon2.exceptions import InvalidHashError

from core.helpers.argon2 import Argon2Helper


def test_hash_password_success():
    # Given
    password = "secure_password123"

    # When
    hashed = Argon2Helper.hash(password)

    # Then
    assert hashed.startswith("$argon2id$")
    assert Argon2Helper.verify(password, hashed) is True


def test_verify_password_failure():
    # Given
    password = "correct_password"
    wrong_password = "wrong_password"
    hashed = Argon2Helper.hash(password)

    # When
    result = Argon2Helper.verify(wrong_password, hashed)

    # Then
    assert result is False


def test_hash_empty_string():
    # Given
    password = ""

    # When
    hashed = Argon2Helper.hash(password)

    # Then
    assert Argon2Helper.verify(password, hashed) is True


def test_verify_with_invalid_hash():
    # Given
    invalid_hash = "not_a_valid_argon2_hash"
    password = "password"

    # When & Then
    with pytest.raises(InvalidHashError):
        Argon2Helper.verify(password, invalid_hash)
