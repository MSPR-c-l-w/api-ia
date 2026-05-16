from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(
    name="X-API-Key",
    description="Clé partagée avec le backend NestJS (`WORKOUT_SERVICE_API_KEY`)",
    auto_error=False,
)


async def verify_api_key(
    x_api_key: str | None = Security(api_key_header),
) -> None:
    if not x_api_key or x_api_key != settings.backend_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_API_KEY",
        )
