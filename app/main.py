"""Application Flask — factory + cycle de vie MongoDB."""

from __future__ import annotations

import asyncio
import atexit

from asgiref.wsgi import WsgiToAsgi
from flask import Flask

from app.config import settings
from app.presentation.exception_handlers import register_error_handlers
from app.presentation.openapi import register_openapi_routes
from app.routers import register_blueprints
from app.shared.infrastructure.database import close_mongodb, connect_mongodb


def create_app() -> Flask:
    application = Flask(__name__)

    register_blueprints(application)
    register_error_handlers(application)
    register_openapi_routes(application)

    if not settings.skip_mongodb_on_startup:
        asyncio.run(connect_mongodb())
        atexit.register(lambda: asyncio.run(close_mongodb()))

    return application


app = create_app()
asgi_app = WsgiToAsgi(app)
