from typing import Protocol

from app.contexts.nutrition.infrastructure.vision.huggingface_provider import (
    VisionDetection,
)
from app.contexts.nutrition.presentation.schemas import (
    DetectedFood,
    EstimatedMacros,
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
)


class VisionProvider(Protocol):
    async def detect_foods(
        self,
        image_url: str | None,
        image_base64: str | None,
    ) -> list[VisionDetection]: ...


class AnalyzeMealUseCase:
    """
    Use case : analyser un repas (vision + recommandations).

    Si un endpoint HF compatible pipeline est configuré, il est utilisé en priorité.
    """

    def __init__(self, vision_providers: list[VisionProvider]) -> None:
        self._vision_providers = vision_providers

    async def execute(self, payload: NutritionAnalysisRequest) -> NutritionAnalysisResponse:
        goal = payload.user_goal or "equilibre"
        image_url = str(payload.image_url) if payload.image_url else None

        provider_labels = ["huggingface", "google_vision"]
        provider_status = "stub"
        detections: list[VisionDetection] = []

        for index, provider in enumerate(self._vision_providers):
            provider_result = await provider.detect_foods(
                image_url=image_url,
                image_base64=payload.image_base64,
            )
            if provider_result:
                detections = provider_result
                provider_status = provider_labels[index]
                break

        if detections:
            detected_foods = [
                DetectedFood(label=item.label, confidence=item.confidence)
                for item in detections
            ]
            model_status = f"{provider_status}_active"
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
