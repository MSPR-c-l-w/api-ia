from fastapi import APIRouter

from app.routers import health, nutrition, recommendations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(nutrition.router, prefix="/api/nutrition", tags=["nutrition"])
api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["recommendations"],
)
