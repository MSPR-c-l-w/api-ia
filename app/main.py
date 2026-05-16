from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.config import settings
from app.openapi_config import (
    OPENAPI_CONTACT,
    OPENAPI_DESCRIPTION,
    OPENAPI_SERVERS,
    OPENAPI_TAGS,
)
from app.routers import api_router
from app.services.database import close_mongodb, connect_mongodb


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not settings.skip_mongodb_on_startup:
        await connect_mongodb()
    yield
    if not settings.skip_mongodb_on_startup:
        await close_mongodb()


def _configure_openapi(application: FastAPI) -> None:
    def custom_openapi():
        if application.openapi_schema:
            return application.openapi_schema

        schema = get_openapi(
            title=settings.api_title,
            version=settings.api_version,
            description=OPENAPI_DESCRIPTION,
            routes=application.routes,
            tags=OPENAPI_TAGS,
            contact=OPENAPI_CONTACT,
            servers=OPENAPI_SERVERS,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})[
            "ApiKeyAuth"
        ] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Clé partagée backend NestJS ↔ micro-service",
        }
        for path, path_item in schema.get("paths", {}).items():
            if path.startswith("/recommendations"):
                for operation in path_item.values():
                    if isinstance(operation, dict):
                        operation["security"] = [{"ApiKeyAuth": []}]
        application.openapi_schema = schema
        return application.openapi_schema

    application.openapi = custom_openapi  # type: ignore[method-assign]


def create_app() -> FastAPI:
    docs_enabled = settings.environment != "production"

    application = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description=OPENAPI_DESCRIPTION,
        contact=OPENAPI_CONTACT,
        openapi_tags=OPENAPI_TAGS,
        servers=OPENAPI_SERVERS,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    application.include_router(api_router)
    _configure_openapi(application)
    return application


app = create_app()
