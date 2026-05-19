"""Compatibilité — voir ``app.shared.infrastructure.database``."""

from app.shared.infrastructure.database import (
    close_mongodb,
    connect_mongodb,
    get_client,
    get_database,
    ping_mongodb,
)

__all__ = [
    "close_mongodb",
    "connect_mongodb",
    "get_client",
    "get_database",
    "ping_mongodb",
]
