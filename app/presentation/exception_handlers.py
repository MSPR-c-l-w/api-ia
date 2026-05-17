"""Gestion des erreurs HTTP pour Flask."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar

from flask import Flask, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

from app.presentation.http import error_response
from app.shared.application.exceptions import (
    ApplicationError,
    InsufficientUserDataError,
    MongoUnavailableError,
    ProgramNotFoundError,
)

T = TypeVar("T")

_STATUS_BY_ERROR: dict[type[ApplicationError], int] = {
    InsufficientUserDataError: 400,
    ProgramNotFoundError: 404,
    MongoUnavailableError: 503,
}


def map_application_errors(
    handler: Callable[..., Awaitable[tuple]],
) -> Callable[..., Awaitable[tuple]]:
    """Décorateur : convertit les ApplicationError en réponses JSON Flask."""

    @wraps(handler)
    async def wrapper(*args, **kwargs):
        try:
            return await handler(*args, **kwargs)
        except ApplicationError as exc:
            status_code = _STATUS_BY_ERROR.get(type(exc), 500)
            return error_response(exc.code, status_code)

    return wrapper


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def handle_validation_error(exc: ValidationError):
        return jsonify({"detail": exc.errors()}), 422

    @app.errorhandler(401)
    def handle_unauthorized(_exc: HTTPException):
        return error_response("INVALID_API_KEY", 401)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return jsonify({"detail": exc.description}), exc.code or 500
