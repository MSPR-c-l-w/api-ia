from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import api_router
from app.services.database import close_mongodb, connect_mongodb


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not settings.skip_mongodb_on_startup:
        await connect_mongodb()
    yield
    if not settings.skip_mongodb_on_startup:
        await close_mongodb()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
    )
    application.include_router(api_router)
    return application


app = create_app()
