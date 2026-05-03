import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.db.session import session, session_context


class RequestScopedDBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        token = session_context.set(str(uuid.uuid4()))
        try:
            return await call_next(request)
        finally:
            await session.remove()
            session_context.reset(token)
