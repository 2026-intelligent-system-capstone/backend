import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.classroom.adapter.output.integration import (
    LLMClassroomMaterialIngestAdapter,
)
from app.exam.adapter.output.integration import (
    LLMExamQuestionGenerationAdapter,
    LLMExamResultEvaluationAdapter,
)
from core.config import config, get_env
from core.db.session import session_context
from core.fastapi import ExtendedFastAPI
from core.fastapi.lifespan import (
    _async_job_worker_loop,
    _validate_poll_interval,
    lifespan,
)
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

    middleware_classes = [middleware.cls for middleware in app.user_middleware]

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
    assert isinstance(
        app.container.exam.result_evaluation_port(),
        LLMExamResultEvaluationAdapter,
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


@pytest.mark.asyncio
async def test_async_job_worker_loop_skips_sleep_when_job_was_handled(
    monkeypatch,
):
    sleep_mock = AsyncMock()
    run_once_mock = AsyncMock(side_effect=[True, asyncio.CancelledError()])
    app = SimpleNamespace(
        settings=SimpleNamespace(ASYNC_JOB_WORKER_POLL_INTERVAL_SECONDS=2.0)
    )

    monkeypatch.setattr(
        "core.fastapi.lifespan._build_async_job_worker", lambda _app: object()
    )
    monkeypatch.setattr(
        "core.fastapi.lifespan._run_async_job_worker_once", run_once_mock
    )
    monkeypatch.setattr("core.fastapi.lifespan.asyncio.sleep", sleep_mock)

    with pytest.raises(asyncio.CancelledError):
        await _async_job_worker_loop(app)

    sleep_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_lifespan_fails_fast_when_poll_interval_is_invalid():
    app = SimpleNamespace(
        settings=SimpleNamespace(
            ASYNC_JOB_WORKER_ENABLED=True,
            ASYNC_JOB_WORKER_POLL_INTERVAL_SECONDS=0,
        )
    )

    with pytest.raises(ValueError, match="must be positive"):
        async with lifespan(app):
            pytest.fail(
                "lifespan should not yield when poll interval is invalid"
            )


@pytest.mark.asyncio
async def test_lifespan_skips_worker_when_async_job_table_is_missing(
    monkeypatch,
):
    build_worker_mock = Mock()
    worker_loop_mock = AsyncMock()
    warning_mock = Mock()

    monkeypatch.setattr(
        "core.fastapi.lifespan._async_job_table_exists",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "core.fastapi.lifespan._build_async_job_worker", build_worker_mock
    )
    monkeypatch.setattr(
        "core.fastapi.lifespan._async_job_worker_loop", worker_loop_mock
    )
    monkeypatch.setattr("core.fastapi.lifespan.logger.warning", warning_mock)

    app = SimpleNamespace(
        settings=SimpleNamespace(
            ASYNC_JOB_WORKER_ENABLED=True,
            ASYNC_JOB_WORKER_POLL_INTERVAL_SECONDS=2.0,
        )
    )

    async with lifespan(app):
        pass

    build_worker_mock.assert_not_called()
    worker_loop_mock.assert_not_awaited()
    warning_mock.assert_called_once_with(
        "Async job worker disabled because %s table does not exist yet",
        "t_async_job",
    )


@pytest.mark.asyncio
async def test_lifespan_fails_fast_when_worker_build_raises(monkeypatch):
    async def unexpected_loop(_app):
        pytest.fail("worker loop should not start when worker build fails")

    def raise_build_error(_app):
        raise RuntimeError("worker build failed")

    monkeypatch.setattr(
        "core.fastapi.lifespan._async_job_worker_loop", unexpected_loop
    )
    monkeypatch.setattr(
        "core.fastapi.lifespan._build_async_job_worker", raise_build_error
    )
    monkeypatch.setattr(
        "core.fastapi.lifespan._async_job_table_exists",
        AsyncMock(return_value=True),
    )

    app = SimpleNamespace(
        settings=SimpleNamespace(
            ASYNC_JOB_WORKER_ENABLED=True,
            ASYNC_JOB_WORKER_POLL_INTERVAL_SECONDS=2.0,
        )
    )

    with pytest.raises(RuntimeError, match="worker build failed"):
        async with lifespan(app):
            pytest.fail("lifespan should not yield when worker build fails")


@pytest.mark.asyncio
async def test_lifespan_cancels_background_worker_on_shutdown(monkeypatch):
    started = asyncio.Event()
    released = asyncio.Event()

    async def blocking_loop(_app, *, worker=None, interval=None):
        _ = (worker, interval)
        started.set()
        await released.wait()

    monkeypatch.setattr(
        "core.fastapi.lifespan._async_job_worker_loop", blocking_loop
    )
    monkeypatch.setattr(
        "core.fastapi.lifespan._build_async_job_worker", lambda _app: object()
    )
    monkeypatch.setattr(
        "core.fastapi.lifespan._async_job_table_exists",
        AsyncMock(return_value=True),
    )

    app = SimpleNamespace(
        settings=SimpleNamespace(
            ASYNC_JOB_WORKER_ENABLED=True,
            ASYNC_JOB_WORKER_POLL_INTERVAL_SECONDS=2.0,
        )
    )

    async with lifespan(app):
        await asyncio.wait_for(started.wait(), timeout=1)

    assert started.is_set()


@pytest.mark.parametrize("interval", [0, -1, -0.1])
def test_validate_poll_interval_rejects_non_positive_value(interval):
    with pytest.raises(ValueError, match="must be positive"):
        _validate_poll_interval(interval)
