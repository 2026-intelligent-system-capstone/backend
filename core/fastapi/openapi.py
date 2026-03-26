from fastapi.dependencies.models import Dependant
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from core.config import config
from core.fastapi import ExtendedFastAPI
from core.fastapi.dependencies.permission import (
    PermissionDependency,
    get_current_user,
)


def configure_openapi_security(app: ExtendedFastAPI) -> None:
    def custom_openapi():
        if app.openapi_schema is not None:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["CookieAuth"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": config.ACCESS_TOKEN_COOKIE_NAME,
        }

        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            if not _requires_cookie_auth(route.dependant):
                continue

            path_item = schema.get("paths", {}).get(route.path)
            if path_item is None:
                continue

            for method in route.methods or []:
                operation = path_item.get(method.lower())
                if operation is None:
                    continue
                operation["security"] = [{"CookieAuth": []}]

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


def _requires_cookie_auth(dependant: Dependant) -> bool:
    for dependency in dependant.dependencies:
        call = dependency.call
        if call is get_current_user:
            return True
        if isinstance(call, PermissionDependency):
            return True
    return False
