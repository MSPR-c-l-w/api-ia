"""Tests unitaires du module d'infrastructure MongoDB partagé.

On manipule les globales du module (``_client`` / ``_database``) via monkeypatch
et on simule Motor pour ne dépendre d'aucune base réelle.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.infrastructure import database


def test_get_client_raises_when_uninitialised(monkeypatch):
    monkeypatch.setattr(database, "_client", None)
    with pytest.raises(RuntimeError, match="MongoDB non initialisé"):
        database.get_client()


def test_get_database_raises_when_uninitialised(monkeypatch):
    monkeypatch.setattr(database, "_database", None)
    with pytest.raises(RuntimeError, match="Base MongoDB non initialisée"):
        database.get_database()


def test_get_client_returns_existing(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(database, "_client", sentinel)
    assert database.get_client() is sentinel


def test_get_database_returns_existing(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(database, "_database", sentinel)
    assert database.get_database() is sentinel


async def test_ping_returns_false_when_no_client(monkeypatch):
    monkeypatch.setattr(database, "_client", None)
    assert await database.ping_mongodb() is False


async def test_ping_returns_true_on_success(monkeypatch):
    client = MagicMock()
    client.admin.command = AsyncMock(return_value={"ok": 1})
    monkeypatch.setattr(database, "_client", client)

    assert await database.ping_mongodb() is True


async def test_ping_returns_false_on_exception(monkeypatch):
    client = MagicMock()
    client.admin.command = AsyncMock(side_effect=RuntimeError("down"))
    monkeypatch.setattr(database, "_client", client)

    assert await database.ping_mongodb() is False


async def test_connect_and_close(monkeypatch):
    fake_db = MagicMock()
    fake_client = MagicMock()
    fake_client.get_default_database.return_value = fake_db
    fake_client.admin.command = AsyncMock(return_value={"ok": 1})

    monkeypatch.setattr(
        database, "AsyncIOMotorClient", MagicMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        "app.shared.infrastructure.indexes.ensure_indexes",
        AsyncMock(return_value=None),
    )

    await database.connect_mongodb()
    assert database.get_client() is fake_client
    assert database.get_database() is fake_db

    await database.close_mongodb()
    fake_client.close.assert_called_once()
    assert database._client is None
    assert database._database is None
