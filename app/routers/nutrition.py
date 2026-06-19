from flask import Blueprint

from app.composition.container import get_container
from app.contexts.nutrition.infrastructure.nutrition_lookup import DEFAULT_SERVING_G
from app.contexts.nutrition.presentation.schemas import (
    MealPlanRequest,
    MealPlanResponse,
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
    PhotoAnalysisResponse,
    PhotoDetectedFood,
    PhotoMacros,
)
from app.dependencies.api_key import require_api_key
from app.presentation.exception_handlers import map_application_errors
from app.presentation.http import model_response, parse_json

nutrition_bp = Blueprint("nutrition", __name__, url_prefix="/ai/nutrition")
nutrition_legacy_bp = Blueprint(
    "nutrition_legacy", __name__, url_prefix="/api/nutrition"
)


@nutrition_bp.post("/analyze")
@map_application_errors
async def analyze_nutrition():
    """Analyse nutritionnelle détaillée (déséquilibres + détails par nutriment)."""
    payload = parse_json(NutritionAnalysisRequest)
    result: NutritionAnalysisResponse = await get_container().analyze_meal.execute(
        payload
    )
    return model_response(result)


@nutrition_bp.post("/analyze-photo")
@require_api_key
@map_application_errors
async def analyze_photo():
    """Détection IA des aliments d'un plat — contrat consommé par le backend NestJS.

    Reçoit ``{ imageUrl, userId }`` (+ biométriques optionnelles), exécute la
    détection vision puis résout chaque aliment via le catalogue MongoDB, et
    renvoie le contrat ``FoodAnalysisResult`` attendu par le backend.
    """
    payload = parse_json(NutritionAnalysisRequest)
    analysis = await get_container().analyze_meal.execute(payload)
    return model_response(_to_food_analysis_result(payload, analysis))


@nutrition_bp.post("/meal-plan")
@map_application_errors
async def generate_meal_plan():
    """Génère un plan repas 7 jours."""
    payload = parse_json(MealPlanRequest)
    result: MealPlanResponse = await get_container().generate_meal_plan.execute(payload)
    return model_response(result)


@nutrition_legacy_bp.post("/analyze")
@map_application_errors
async def analyze_nutrition_legacy():
    """Alias historique `/api/nutrition/analyze` pour compatibilité."""
    payload = parse_json(NutritionAnalysisRequest)
    result: NutritionAnalysisResponse = await get_container().analyze_meal.execute(
        payload
    )
    return model_response(result)


def _to_food_analysis_result(
    payload: NutritionAnalysisRequest, analysis: NutritionAnalysisResponse
) -> PhotoAnalysisResponse:
    """Mappe la réponse d'analyse riche vers le contrat attendu par le backend."""
    return PhotoAnalysisResponse(
        image_url=str(payload.image_url) if payload.image_url else "",
        aliments_detectes=[
            PhotoDetectedFood(
                name=food.label,
                quantity_g=DEFAULT_SERVING_G,
                confidence=food.confidence,
            )
            for food in analysis.detected_foods
        ],
        macros=PhotoMacros(
            calories=analysis.estimated_calories,
            protein_g=analysis.estimated_macros.proteins_g,
            carbs_g=analysis.estimated_macros.carbs_g,
            fat_g=analysis.estimated_macros.fats_g,
        ),
        suggestions=analysis.feedback,
        model_status=analysis.model_status,
    )
