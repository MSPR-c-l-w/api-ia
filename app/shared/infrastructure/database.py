from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    if _client is None:
        raise RuntimeError("MongoDB non initialisé")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    if _database is None:
        raise RuntimeError("Base MongoDB non initialisée")
    return _database


async def connect_mongodb() -> None:
    global _client, _database
    from app.shared.infrastructure.indexes import ensure_indexes

    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _database = _client.get_default_database()
    await _client.admin.command("ping")
    await ensure_indexes(_database)


async def close_mongodb() -> None:
    global _client, _database
    if _client is not None:
        _client.close()
    _client = None
    _database = None


async def ping_mongodb() -> bool:
    if _client is None:
        return False
    try:
        await _client.admin.command("ping")
        return True
    except Exception:
        return False
