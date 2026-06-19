"""Tests de l'enveloppe ASGI _LifespanAsgiApp (cycle de vie MongoDB)."""

from unittest.mock import AsyncMock, MagicMock, patch

from app import main
from app.main import _LifespanAsgiApp, create_app


def test_create_app_returns_flask():
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/health" in rules


class _LifespanDriver:
    """Simule le protocole ASGI lifespan : startup puis shutdown."""

    def __init__(self):
        self._events = iter(
            [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]
        )
        self.sent: list[dict] = []

    async def receive(self):
        return next(self._events)

    async def send(self, message):
        self.sent.append(message)


async def test_lifespan_skips_mongodb_in_test_mode():
    asgi = _LifespanAsgiApp(create_app())
    driver = _LifespanDriver()

    # En env test, skip_mongodb_on_startup = True → pas de connexion Motor.
    await asgi({"type": "lifespan"}, driver.receive, driver.send)

    types = [m["type"] for m in driver.sent]
    assert types == ["lifespan.startup.complete", "lifespan.shutdown.complete"]


async def test_lifespan_connects_when_not_skipped():
    asgi = _LifespanAsgiApp(create_app())
    driver = _LifespanDriver()

    connect = AsyncMock()
    close = AsyncMock()
    with (
        patch.object(main.settings, "environment", "production"),
        patch.object(main, "connect_mongodb", connect),
        patch.object(main, "close_mongodb", close),
    ):
        await asgi({"type": "lifespan"}, driver.receive, driver.send)

    connect.assert_awaited_once()
    close.assert_awaited_once()


async def test_non_lifespan_scope_delegates_to_wsgi():
    asgi = _LifespanAsgiApp(create_app())
    asgi._asgi = AsyncMock()
    scope = {"type": "http"}
    receive, send = MagicMock(), MagicMock()

    await asgi(scope, receive, send)

    asgi._asgi.assert_awaited_once_with(scope, receive, send)
