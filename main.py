import logging

from app.container import AppContainer
from core.config import config, get_env
from core.db.sqlalchemy import init_orm_mappers
from core.fastapi import ExtendedFastAPI
from core.fastapi.lifespan import lifespan
from core.fastapi.listener import register_handlers
from core.fastapi.middlewares import make_middleware
from core.fastapi.openapi import configure_openapi_security
from core.fastapi.router import register_routers


def create_app() -> ExtendedFastAPI:
    env = get_env()
    container = AppContainer()

    init_orm_mappers()

    app_ = ExtendedFastAPI(
        title=config.APP_NAME,
        description=config.APP_DESCRIPTION,
        version=config.APP_VERSION,
        env=env,
        settings=config,
        middleware=make_middleware(),
        lifespan=lifespan,
        docs_url=config.DOCS_URL,
        redoc_url=config.REDOC_URL,
        openapi_url=config.OPENAPI_URL,
    )
    app_.container = container

    register_routers(app_)
    configure_openapi_security(app_)
    register_handlers(app_)

    logger = logging.getLogger(__name__)
    logger.info("Application bootstrap completed", extra={"env": env})

    return app_


app = create_app()
