from unittest.mock import AsyncMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.classroom.adapter.output.integration import (
    LLMClassroomMaterialIngestAdapter,
)
from app.exam.adapter.output.integration import (
    LLMExamQuestionGenerationAdapter,
)
from core.config import config, get_env
from core.db.session import session_context
from core.fastapi import ExtendedFastAPI
from core.fastapi.middlewares.request_scoped_db_session import (
    RequestScopedDBSessionMiddleware,
)
from main import create_app


def test_create_app_returns_extended_fastapi():
    app = create_app()

    assert isinstance(app, ExtendedFastAPI)
    assert app.title == config.APP_NAME
    assert app.env == get_env()
    assert app.openapi_url == config.OPENAPI_URL
    assert app.docs_url == config.DOCS_URL


def test_app_registers_health_check_route():
    app = create_app()

    paths = {route.path for route in app.routes}

    assert f"{config.API_PREFIX}/healthz" in paths


def test_app_openapi_registers_cookie_auth_security_scheme():
    app = create_app()

    schema = app.openapi()

    assert schema["components"]["securitySchemes"]["CookieAuth"] == {
        "type": "apiKey",
        "in": "cookie",
        "name": config.ACCESS_TOKEN_COOKIE_NAME,
    }


def test_app_openapi_marks_authenticated_routes_with_security():
    app = create_app()

    schema = app.openapi()

    assert schema["paths"][f"{config.API_PREFIX}/users"]["get"]["security"] == [
        {"CookieAuth": []}
    ]
    assert (
        "security"
        not in schema["paths"][f"{config.API_PREFIX}/users/{{user_id}}"]["get"]
    )


def test_app_registers_request_scoped_db_session_middleware():
    app = create_app()

    middleware_classes = [
        middleware.cls for middleware in app.user_middleware
    ]

    assert RequestScopedDBSessionMiddleware in middleware_classes


def test_create_app_registers_llm_adapters():
    app = create_app()

    assert isinstance(
        app.container.classroom.material_ingest_port(),
        LLMClassroomMaterialIngestAdapter,
    )
    assert isinstance(
        app.container.exam.question_generation_port(),
        LLMExamQuestionGenerationAdapter,
    )


def test_request_scoped_session_resets_context_and_removes_session(
    monkeypatch,
):
    app = create_app()

    remove_mock = AsyncMock()
    monkeypatch.setattr(
        "core.fastapi.middlewares.request_scoped_db_session.session.remove",
        remove_mock,
    )

    @app.get("/test/session-scope")
    async def test_route():
        assert session_context.get() != "global"
        raise HTTPException(status_code=418, detail="boom")

    with TestClient(app) as client:
        response = client.get("/test/session-scope")

    assert response.status_code == 418
    remove_mock.assert_awaited_once()
    assert session_context.get() == "global"
