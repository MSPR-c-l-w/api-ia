from fastapi import APIRouter

from app.models.schemas import NutritionAnalysisRequest, NutritionAnalysisResponse

router = APIRouter()


@router.post(
    "/analyze",
    response_model=NutritionAnalysisResponse,
    summary="Analyser un repas (stub)",
    description=(
        "Analyse nutritionnelle à partir d'une image ou d'un objectif utilisateur. "
        "Implémentation stub en attendant l'intégration Hugging Face."
    ),
    responses={
        422: {"description": "Corps de requête invalide"},
    },
)
async def analyze_nutrition(
    payload: NutritionAnalysisRequest,
) -> NutritionAnalysisResponse:
    goal = payload.user_goal or "equilibre"

    return NutritionAnalysisResponse(
        detected_foods=[{"label": "poulet-riz", "confidence": 0.84}],
        estimated_calories=520,
        estimated_macros={
            "proteins_g": 32,
            "carbs_g": 54,
            "fats_g": 14,
        },
        feedback=[
            f"Repas compatible avec un objectif de {goal}.",
            "Ajouter une source de fibres peut ameliorer l'equilibre nutritionnel.",
        ],
        model_status="stub_ready_for_huggingface",
    )
