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
