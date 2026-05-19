"""Authentification inter-services — header X-API-Key (#99)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar

from flask import request
from werkzeug.exceptions import Unauthorized

from app.config import settings

T = TypeVar("T")


def require_api_key(
    handler: Callable[..., Awaitable[T]],
) -> Callable[..., Awaitable[T]]:
    """Décorateur Flask : exige une clé API valide."""

    @wraps(handler)
    async def wrapper(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != settings.backend_api_key:
            raise Unauthorized(description="INVALID_API_KEY")
        return await handler(*args, **kwargs)

    return wrapper
