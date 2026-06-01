"""Helpers HTTP Flask — validation Pydantic et réponses JSON (alias camelCase)."""

from __future__ import annotations

from typing import TypeVar

from flask import Response, jsonify, request
from pydantic import BaseModel, ValidationError

TModel = TypeVar("TModel", bound=BaseModel)


def parse_json(model: type[TModel]) -> TModel:
    """Valide le corps JSON entrant avec un modèle Pydantic."""
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError.from_exception_data(
            model.__name__,
            [{"type": "missing", "loc": ("body",), "msg": "Corps JSON requis"}],
        )
    return model.model_validate(data)


def model_response(model: BaseModel, status: int = 200) -> tuple[Response, int]:
    """Sérialise un modèle Pydantic avec les alias (camelCase API)."""
    return jsonify(model.model_dump(by_alias=True, mode="json")), status


def error_response(code: str, status: int) -> tuple[Response, int]:
    """Format d'erreur aligné sur l'ancienne API FastAPI (`detail` = code métier)."""
    return jsonify({"detail": code}), status
