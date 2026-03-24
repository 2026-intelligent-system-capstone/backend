from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


class Argon2Helper:
    _ph = PasswordHasher()

    @classmethod
    def hash(cls, password: str) -> str:
        """
        Hash a password using Argon2id.
        """
        return cls._ph.hash(password)

    @classmethod
    def verify(cls, password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hash.
        """
        try:
            return cls._ph.verify(hashed_password, password)
        except VerifyMismatchError:
            return False
        except Exception as e:
            # Re-raise for malformed hashes or other critical errors to be caught by tests/apps
            raise e
