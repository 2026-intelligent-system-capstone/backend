from contextlib import asynccontextmanager

from core.fastapi import ExtendedFastAPI


@asynccontextmanager
async def lifespan(_app: ExtendedFastAPI):
    yield
