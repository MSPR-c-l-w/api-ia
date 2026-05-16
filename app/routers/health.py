from datetime import UTC, datetime

from fastapi import APIRouter

from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Sonde de santé",
    description="Vérifie que l'API répond. Aucune authentification requise.",
)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.now(UTC))
