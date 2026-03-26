from uuid import UUID

import pytest

from app.auth.adapter.output.persistence.valkey.auth_token import (
    ValkeyAuthTokenRepository,
)

USER_ID = UUID("11111111-1111-1111-1111-111111111111")
JTI = "refresh-jti"


class FakeValkeyClient:
    def __init__(self):
        self.storage: dict[str, str | bytes] = {}
        self.expirations: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int) -> None:
        self.storage[key] = value
        self.expirations[key] = ex

    async def get(self, key: str) -> str | bytes | None:
        return self.storage.get(key)

    async def delete(self, key: str) -> None:
        self.storage.pop(key, None)
        self.expirations.pop(key, None)


@pytest.mark.asyncio
async def test_save_stores_refresh_token_with_expiry():
    client = FakeValkeyClient()
    repository = ValkeyAuthTokenRepository(client=client)

    await repository.save(
        user_id=USER_ID,
        jti=JTI,
        refresh_token="refresh-token",
        expires_in=3600,
    )

    key = repository._build_key(user_id=USER_ID, jti=JTI)

    assert client.storage[key] == "refresh-token"
    assert client.expirations[key] == 3600


@pytest.mark.asyncio
async def test_get_returns_decoded_token_when_client_returns_bytes():
    client = FakeValkeyClient()
    repository = ValkeyAuthTokenRepository(client=client)
    key = repository._build_key(user_id=USER_ID, jti=JTI)
    client.storage[key] = b"stored-refresh-token"

    token = await repository.get(user_id=USER_ID, jti=JTI)

    assert token == "stored-refresh-token"


@pytest.mark.asyncio
async def test_delete_removes_refresh_token():
    client = FakeValkeyClient()
    repository = ValkeyAuthTokenRepository(client=client)
    key = repository._build_key(user_id=USER_ID, jti=JTI)
    client.storage[key] = "stored-refresh-token"
    client.expirations[key] = 3600

    await repository.delete(user_id=USER_ID, jti=JTI)

    assert key not in client.storage
    assert key not in client.expirations
