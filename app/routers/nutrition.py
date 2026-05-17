from flask import Blueprint

from app.composition.container import get_container
from app.contexts.nutrition.presentation.schemas import (
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
)
from app.presentation.http import model_response, parse_json

nutrition_bp = Blueprint("nutrition", __name__, url_prefix="/api/nutrition")


@nutrition_bp.post("/analyze")
async def analyze_nutrition():
    """Analyse nutritionnelle (stub — intégration Hugging Face à venir)."""
    payload = parse_json(NutritionAnalysisRequest)
    result: NutritionAnalysisResponse = await get_container().analyze_meal.execute(payload)
    return model_response(result)
