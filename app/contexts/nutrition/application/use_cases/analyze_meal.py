from app.contexts.nutrition.presentation.schemas import (
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
)


class AnalyzeMealUseCase:
    """
    Use case : analyser un repas (vision + recommandations).

    Stub en attendant l'intégration Hugging Face / Google Vision (MSPR § II.1).
    """

    async def execute(self, payload: NutritionAnalysisRequest) -> NutritionAnalysisResponse:
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
