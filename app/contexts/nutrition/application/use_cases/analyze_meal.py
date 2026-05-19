from app.contexts.nutrition.infrastructure.vision.huggingface_provider import (
    HuggingFaceVisionProvider,
)
from app.contexts.nutrition.presentation.schemas import (
    DetectedFood,
    EstimatedMacros,
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
)


class AnalyzeMealUseCase:
    """
    Use case : analyser un repas (vision + recommandations).

    Si un endpoint HF compatible pipeline est configuré, il est utilisé en priorité.
    """

    def __init__(self, hf_provider: HuggingFaceVisionProvider) -> None:
        self._hf_provider = hf_provider

    async def execute(self, payload: NutritionAnalysisRequest) -> NutritionAnalysisResponse:
        goal = payload.user_goal or "equilibre"

        detections = await self._hf_provider.detect_foods(
            image_url=str(payload.image_url) if payload.image_url else None,
            image_base64=payload.image_base64,
        )

        if detections:
            detected_foods = [
                DetectedFood(label=item.label, confidence=item.confidence)
                for item in detections
            ]
            model_status = "huggingface_active"
            estimated_calories = 200 + (120 * len(detected_foods))
        else:
            detected_foods = [DetectedFood(label="poulet-riz", confidence=0.84)]
            model_status = "stub_ready_for_huggingface"
            estimated_calories = 520

        return NutritionAnalysisResponse(
            detected_foods=detected_foods,
            estimated_calories=estimated_calories,
            estimated_macros=EstimatedMacros(proteins_g=32, carbs_g=54, fats_g=14),
            feedback=[
                f"Repas compatible avec un objectif de {goal}.",
                "Ajouter une source de fibres peut ameliorer l'equilibre nutritionnel.",
            ],
            model_status=model_status,
        )
