from fastapi import FastAPI

from app.user.adapter.input.api.v1.user import router as user_router
from core.db.sqlalchemy import init_orm_mappers


def create_app() -> FastAPI:
    init_orm_mappers()

    app = FastAPI(title="Development Outsourcing Platform")
    app.include_router(user_router)
    return app
