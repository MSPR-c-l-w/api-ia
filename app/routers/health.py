from datetime import UTC, datetime

from flask import Blueprint

from app.models.schemas import HealthResponse
from app.presentation.http import model_response

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
async def health_check():
    """Sonde de santé — aucune authentification requise."""
    return model_response(HealthResponse(status="ok", timestamp=datetime.now(UTC)))
