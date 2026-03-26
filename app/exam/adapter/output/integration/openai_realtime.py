from datetime import UTC, datetime

import httpx

from app.exam.domain.entity import RealtimeClientSecret
from app.exam.domain.service import RealtimeSessionPort
from core.config import config


class OpenAIRealtimeSessionAdapter(RealtimeSessionPort):
    async def create_client_secret(
        self,
        *,
        instructions: str,
    ) -> RealtimeClientSecret:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/realtime/client_secrets",
                headers={
                    "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "expires_after": {
                        "anchor": "created_at",
                        "seconds": config.OPENAI_REALTIME_SECRET_EXPIRE_SECONDS,
                    },
                    "session": {
                        "type": "realtime",
                        "model": config.OPENAI_REALTIME_MODEL,
                        "instructions": instructions,
                        "audio": {
                            "output": {
                                "voice": config.OPENAI_REALTIME_VOICE,
                            }
                        },
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()

        expires_at = None
        if payload.get("expires_at") is not None:
            expires_at = datetime.fromtimestamp(payload["expires_at"], UTC)

        session_payload = payload.get("session") or {}
        return RealtimeClientSecret(
            value=payload["value"],
            expires_at=expires_at,
            provider_session_id=session_payload.get("id"),
        )
