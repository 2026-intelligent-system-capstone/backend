from uuid import UUID

from valkey.asyncio import Valkey

from app.auth.domain.repository import AuthTokenRepository


class ValkeyAuthTokenRepository(AuthTokenRepository):
    def __init__(self, *, client: Valkey):
        self.client = client

    async def save(
        self,
        *,
        user_id: UUID,
        jti: str,
        refresh_token: str,
        expires_in: int,
    ) -> None:
        await self.client.set(
            self._build_key(user_id=user_id, jti=jti),
            refresh_token,
            ex=expires_in,
        )

    async def get(self, *, user_id: UUID, jti: str) -> str | None:
        token = await self.client.get(self._build_key(user_id=user_id, jti=jti))
        if token is None:
            return None
        if isinstance(token, bytes):
            return token.decode()
        return token

    async def delete(self, *, user_id: UUID, jti: str) -> None:
        await self.client.delete(self._build_key(user_id=user_id, jti=jti))

    @staticmethod
    def _build_key(*, user_id: UUID, jti: str) -> str:
        return f"auth:user:{user_id}:refresh:{jti}"
