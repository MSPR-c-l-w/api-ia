"""Application Flask — factory + cycle de vie MongoDB."""

from __future__ import annotations

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

    return application


class _LifespanAsgiApp:
    """ASGI wrapper that handles lifespan events in Hypercorn's own event loop.

    Problem solved: ``asyncio.run(connect_mongodb())`` created the Motor client
    on a throwaway loop that was immediately closed.  When Hypercorn later ran
    its own loop all Motor awaits failed with "Future attached to a different
    loop".

    Solution: defer the MongoDB connection to the ASGI ``lifespan.startup``
    event, which runs inside Hypercorn's loop.  The Motor client is therefore
    bound to the correct, long-lived loop for the entire lifetime of the server.
    """

    def __init__(self, wsgi_app: Flask) -> None:
        self._asgi = WsgiToAsgi(wsgi_app)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "lifespan":
            while True:
                event = await receive()
                if event["type"] == "lifespan.startup":
                    if not settings.skip_mongodb_on_startup:
                        await connect_mongodb()
                    await send({"type": "lifespan.startup.complete"})
                elif event["type"] == "lifespan.shutdown":
                    if not settings.skip_mongodb_on_startup:
                        await close_mongodb()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        else:
            await self._asgi(scope, receive, send)


app = create_app()
asgi_app = _LifespanAsgiApp(app)
