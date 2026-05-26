from flask import Blueprint

from app.composition.container import get_container
from app.contexts.nutrition.presentation.schemas import (
    MealPlanRequest,
    MealPlanResponse,
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
)
from app.presentation.exception_handlers import map_application_errors
from app.presentation.http import model_response, parse_json

nutrition_bp = Blueprint("nutrition", __name__, url_prefix="/ai/nutrition")
nutrition_legacy_bp = Blueprint("nutrition_legacy", __name__, url_prefix="/api/nutrition")


@nutrition_bp.post("/analyze")
@map_application_errors
async def analyze_nutrition():
    """Analyse nutritionnelle (stub — intégration vision à venir)."""
    payload = parse_json(NutritionAnalysisRequest)
    result: NutritionAnalysisResponse = await get_container().analyze_meal.execute(payload)
    return model_response(result)


@nutrition_bp.post("/meal-plan")
@map_application_errors
async def generate_meal_plan():
    """Génère un plan repas 7 jours (stub — intégration LLM à venir)."""
    payload = parse_json(MealPlanRequest)
    result: MealPlanResponse = await get_container().generate_meal_plan.execute(payload)
    return model_response(result)


@nutrition_legacy_bp.post("/analyze")
@map_application_errors
async def analyze_nutrition_legacy():
    """Alias historique `/api/nutrition/analyze` pour compatibilité."""
    payload = parse_json(NutritionAnalysisRequest)
    result: NutritionAnalysisResponse = await get_container().analyze_meal.execute(payload)
    return model_response(result)
