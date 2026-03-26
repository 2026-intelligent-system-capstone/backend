from abc import ABC, abstractmethod

from app.exam.domain.entity import RealtimeClientSecret


class RealtimeSessionPort(ABC):
    @abstractmethod
    async def create_client_secret(
        self,
        *,
        instructions: str,
    ) -> RealtimeClientSecret:
        """Create a GPT Realtime client secret for the exam session."""
