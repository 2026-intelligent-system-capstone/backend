from core.config import config, get_env
from core.fastapi import ExtendedFastAPI
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
